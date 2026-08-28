import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as elasticache from 'aws-cdk-lib/aws-elasticache';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import { Construct } from 'constructs';
import { NetworkStack } from './network-stack';

export interface DatabaseStackProps extends cdk.StackProps {
  networkStack: NetworkStack;
  /** Logical environment name used for resource naming and CFN exports. */
  envName?: string;
}

/**
 * DatabaseStack provisions the persistence layer:
 * - RDS PostgreSQL 16 (db.t3.micro, encrypted at rest, private subnet only)
 * - RDS Proxy for connection pooling with mandatory TLS
 * - ElastiCache Redis single-node cluster (cache.t3.micro, in-transit encryption)
 *
 * Multi-AZ is disabled for dev/Phase-1 cost targets (<$100/month). Enable
 * multiAz and increase instance class for production.
 */
export class DatabaseStack extends cdk.Stack {
  /** Auto-generated RDS credentials secret (username + password JSON). */
  public readonly dbSecret: secretsmanager.ISecret;
  /** RDS Proxy endpoint — ECS tasks should connect here, not directly to RDS. */
  public readonly dbProxy: rds.DatabaseProxy;
  /** ElastiCache Redis cluster CFN resource. */
  public readonly redisCluster: elasticache.CfnCacheCluster;

  constructor(scope: Construct, id: string, props: DatabaseStackProps) {
    super(scope, id, props);

    const { networkStack } = props;
    const envName = props.envName ?? 'dev';

    // ── RDS PostgreSQL 16 ──────────────────────────────────────────────────
    const dbInstance = new rds.DatabaseInstance(this, 'PostgresInstance', {
      engine: rds.DatabaseInstanceEngine.postgres({
        version: rds.PostgresEngineVersion.VER_16,
      }),
      // db.t3.micro keeps Phase-1 cost under $100/month.
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
      vpc: networkStack.vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      securityGroups: [networkStack.rdsSecurityGroup],
      // Multi-AZ disabled for dev cost savings; enable for production.
      multiAz: false,
      storageEncrypted: true,
      allocatedStorage: 20,
      maxAllocatedStorage: 100,
      databaseName: 'ashtachamma',
      // Auto-generate credentials and store in Secrets Manager.
      credentials: rds.Credentials.fromGeneratedSecret('postgres', {
        secretName: `${envName}/ashtachamma/db-credentials`,
      }),
      // RDS must not be publicly accessible — private subnet only.
      publiclyAccessible: false,
      deletionProtection: false,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      backupRetention: cdk.Duration.days(7),
      instanceIdentifier: `${envName}-ashta-chamma-postgres`,
    });

    // The secret is created automatically by fromGeneratedSecret.
    this.dbSecret = dbInstance.secret!;

    // ── RDS Proxy ──────────────────────────────────────────────────────────
    // Proxy pools connections from Fargate tasks; reduces RDS connection churn
    // under auto-scaling. Placed in same security group as RDS.
    this.dbProxy = new rds.DatabaseProxy(this, 'RdsProxy', {
      proxyTarget: rds.ProxyTarget.fromInstance(dbInstance),
      secrets: [this.dbSecret],
      vpc: networkStack.vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      securityGroups: [networkStack.rdsSecurityGroup],
      requireTLS: true,
      dbProxyName: `${envName}-ashta-chamma-proxy`,
    });

    // ── ElastiCache Redis ──────────────────────────────────────────────────
    const redisSubnetGroup = new elasticache.CfnSubnetGroup(this, 'RedisSubnetGroup', {
      description: `${envName} ElastiCache Redis subnet group`,
      subnetIds: networkStack.vpc.privateSubnets.map((s) => s.subnetId),
      cacheSubnetGroupName: `${envName}-redis-subnet-group`,
    });

    // Single-node Redis cluster (cache.t3.micro) for Phase-1 cost target.
    // In-transit encryption enforced; no AUTH token required at ElastiCache level
    // for dev — the app reads the token from Secrets Manager when connecting.
    this.redisCluster = new elasticache.CfnCacheCluster(this, 'RedisCluster', {
      clusterName: `${envName}-ashta-chamma-redis`,
      cacheNodeType: 'cache.t3.micro',
      engine: 'redis',
      numCacheNodes: 1,
      cacheSubnetGroupName: redisSubnetGroup.cacheSubnetGroupName,
      vpcSecurityGroupIds: [networkStack.redisSecurityGroup.securityGroupId],
      // Enforce TLS for all Redis connections (in-transit encryption).
      transitEncryptionEnabled: true,
    });
    this.redisCluster.addDependency(redisSubnetGroup);

    // ── CloudFormation outputs ──────────────────────────────────────────────
    new cdk.CfnOutput(this, 'DbProxyEndpoint', {
      value: this.dbProxy.endpoint,
      description: 'RDS Proxy endpoint — use this for application DB connections',
      exportName: `${envName}-DbProxyEndpoint`,
    });
    new cdk.CfnOutput(this, 'RedisEndpoint', {
      value: this.redisCluster.attrRedisEndpointAddress,
      description: 'ElastiCache Redis primary endpoint',
      exportName: `${envName}-RedisEndpoint`,
    });
    new cdk.CfnOutput(this, 'RedisPort', {
      value: this.redisCluster.attrRedisEndpointPort,
      description: 'ElastiCache Redis port',
      exportName: `${envName}-RedisPort`,
    });
    new cdk.CfnOutput(this, 'DbSecretArn', {
      value: this.dbSecret.secretArn,
      description: 'ARN of the RDS credentials secret in Secrets Manager',
      exportName: `${envName}-DbSecretArn`,
    });
  }
}
