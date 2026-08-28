import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

export interface NetworkStackProps extends cdk.StackProps {
  /** Logical environment name used for resource naming and CFN exports. */
  envName?: string;
}

/**
 * NetworkStack provisions the foundational VPC networking layer:
 * - VPC with 2 public and 2 private subnets across 2 AZs
 * - Single NAT gateway for cost-efficiency in dev
 * - Security groups with least-privilege rules for ALB, ECS, RDS, and Redis
 */
export class NetworkStack extends cdk.Stack {
  public readonly vpc: ec2.Vpc;
  public readonly albSecurityGroup: ec2.SecurityGroup;
  public readonly ecsSecurityGroup: ec2.SecurityGroup;
  public readonly rdsSecurityGroup: ec2.SecurityGroup;
  public readonly redisSecurityGroup: ec2.SecurityGroup;

  constructor(scope: Construct, id: string, props?: NetworkStackProps) {
    super(scope, id, props);

    const envName = props?.envName ?? 'dev';

    // VPC: 2 public + 2 private subnets across 2 AZs, single NAT for dev cost savings.
    this.vpc = new ec2.Vpc(this, 'AppVpc', {
      maxAzs: 2,
      natGateways: 1,
      subnetConfiguration: [
        {
          cidrMask: 24,
          name: 'Public',
          subnetType: ec2.SubnetType.PUBLIC,
        },
        {
          cidrMask: 24,
          name: 'Private',
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
        },
      ],
      vpcName: `${envName}-ashta-chamma-vpc`,
    });

    // ALB security group: accepts HTTP (port 80, for redirect) and HTTPS (port 443) from internet.
    this.albSecurityGroup = new ec2.SecurityGroup(this, 'AlbSecurityGroup', {
      vpc: this.vpc,
      securityGroupName: `${envName}-alb-sg`,
      description: 'Security group for Application Load Balancer — allows HTTP/HTTPS from internet',
      allowAllOutbound: true,
    });
    this.albSecurityGroup.addIngressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(80),
      'Allow HTTP for redirect to HTTPS',
    );
    this.albSecurityGroup.addIngressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(443),
      'Allow HTTPS from internet',
    );

    // ECS security group: only accepts application traffic from the ALB.
    this.ecsSecurityGroup = new ec2.SecurityGroup(this, 'EcsSecurityGroup', {
      vpc: this.vpc,
      securityGroupName: `${envName}-ecs-sg`,
      description: 'Security group for ECS Fargate tasks — inbound from ALB only',
      allowAllOutbound: true,
    });
    this.ecsSecurityGroup.addIngressRule(
      this.albSecurityGroup,
      ec2.Port.tcp(8000),
      'Allow application traffic from ALB',
    );

    // RDS security group: only accepts PostgreSQL connections from ECS tasks.
    // allowAllOutbound is true so the RDS Proxy (also placed in this SG) can
    // reach Secrets Manager via the NAT gateway for credential retrieval.
    this.rdsSecurityGroup = new ec2.SecurityGroup(this, 'RdsSecurityGroup', {
      vpc: this.vpc,
      securityGroupName: `${envName}-rds-sg`,
      description: 'Security group for RDS PostgreSQL and RDS Proxy — inbound from ECS only',
      allowAllOutbound: true,
    });
    this.rdsSecurityGroup.addIngressRule(
      this.ecsSecurityGroup,
      ec2.Port.tcp(5432),
      'Allow PostgreSQL from ECS tasks',
    );
    // Self-referencing rule: allows RDS Proxy (in same SG) to reach RDS instance.
    this.rdsSecurityGroup.addIngressRule(
      this.rdsSecurityGroup,
      ec2.Port.tcp(5432),
      'Allow PostgreSQL from RDS Proxy (same SG)',
    );

    // Redis security group: only accepts Redis connections from ECS tasks.
    this.redisSecurityGroup = new ec2.SecurityGroup(this, 'RedisSecurityGroup', {
      vpc: this.vpc,
      securityGroupName: `${envName}-redis-sg`,
      description: 'Security group for ElastiCache Redis — inbound from ECS only',
      allowAllOutbound: false,
    });
    this.redisSecurityGroup.addIngressRule(
      this.ecsSecurityGroup,
      ec2.Port.tcp(6379),
      'Allow Redis from ECS tasks',
    );

    // ── CloudFormation outputs ──────────────────────────────────────────────
    new cdk.CfnOutput(this, 'VpcId', {
      value: this.vpc.vpcId,
      description: 'VPC identifier',
      exportName: `${envName}-VpcId`,
    });
    new cdk.CfnOutput(this, 'AlbSecurityGroupId', {
      value: this.albSecurityGroup.securityGroupId,
      description: 'ALB security group ID',
      exportName: `${envName}-AlbSgId`,
    });
    new cdk.CfnOutput(this, 'EcsSecurityGroupId', {
      value: this.ecsSecurityGroup.securityGroupId,
      description: 'ECS Fargate task security group ID',
      exportName: `${envName}-EcsSgId`,
    });
    new cdk.CfnOutput(this, 'RdsSecurityGroupId', {
      value: this.rdsSecurityGroup.securityGroupId,
      description: 'RDS PostgreSQL security group ID',
      exportName: `${envName}-RdsSgId`,
    });
    new cdk.CfnOutput(this, 'RedisSecurityGroupId', {
      value: this.redisSecurityGroup.securityGroupId,
      description: 'ElastiCache Redis security group ID',
      exportName: `${envName}-RedisSgId`,
    });
  }
}
