import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import { NetworkStack } from './network-stack';

export interface ComputeStackProps extends cdk.StackProps {
  networkStack: NetworkStack;
  /** ARN of the RDS credentials Secrets Manager secret. */
  dbSecretArn: string;
  /** Logical environment name used for resource naming and CFN exports. */
  envName?: string;
}

/**
 * ComputeStack provisions the application compute layer:
 * - ECR repository for the FastAPI container image
 * - ECS Fargate cluster + task definition (0.25 vCPU / 512 MB)
 * - Application Load Balancer with HTTP→HTTPS redirect and HTTPS listener
 * - Target group with /api/health health check
 * - Auto-scaling configuration (min 1, max 4 tasks for dev)
 *
 * The HTTPS listener requires an ACM certificate. Provide the ARN via the
 * AcmCertificateArn CloudFormation parameter at deploy time.
 */
export class ComputeStack extends cdk.Stack {
  public readonly alb: elbv2.ApplicationLoadBalancer;
  public readonly ecrRepository: ecr.Repository;
  public readonly fargateService: ecs.FargateService;

  constructor(scope: Construct, id: string, props: ComputeStackProps) {
    super(scope, id, props);

    const { networkStack } = props;
    const envName = props.envName ?? 'dev';

    // ── ECR Repository ─────────────────────────────────────────────────────
    this.ecrRepository = new ecr.Repository(this, 'AppRepository', {
      repositoryName: `${envName}-ashta-chamma-api`,
      imageScanOnPush: true,
      // Remove the repo when the stack is destroyed in dev environments.
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      emptyOnDelete: true,
    });

    // ── ECS Cluster ────────────────────────────────────────────────────────
    const cluster = new ecs.Cluster(this, 'AppCluster', {
      vpc: networkStack.vpc,
      clusterName: `${envName}-ashta-chamma-cluster`,
      // Container Insights for CloudWatch metrics on tasks and services.
      containerInsights: true,
    });

    // ── IAM Roles ──────────────────────────────────────────────────────────
    // Task execution role: pulled from ECR, writes CloudWatch logs.
    const taskExecutionRole = new iam.Role(this, 'TaskExecutionRole', {
      roleName: `${envName}-ashta-chamma-task-execution-role`,
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          'service-role/AmazonECSTaskExecutionRolePolicy',
        ),
      ],
    });

    // Task role: runtime permissions for the application process.
    const taskRole = new iam.Role(this, 'TaskRole', {
      roleName: `${envName}-ashta-chamma-task-role`,
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
    });
    // Least-privilege: only allow reading the DB credentials secret.
    taskRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ['secretsmanager:GetSecretValue'],
        resources: [props.dbSecretArn],
      }),
    );

    // ── CloudWatch Log Group ───────────────────────────────────────────────
    const logGroup = new logs.LogGroup(this, 'AppLogGroup', {
      logGroupName: `/ecs/${envName}-ashta-chamma`,
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // ── Fargate Task Definition ────────────────────────────────────────────
    // 0.25 vCPU / 512 MB: lowest Fargate combination, meets Phase-1 cost target.
    const taskDefinition = new ecs.FargateTaskDefinition(this, 'AppTaskDef', {
      memoryLimitMiB: 512,
      cpu: 256,
      executionRole: taskExecutionRole,
      taskRole,
      family: `${envName}-ashta-chamma-task`,
    });

    // Placeholder image — real image is pushed by the CI/CD pipeline (WO-003).
    taskDefinition.addContainer('ApiContainer', {
      containerName: 'api',
      image: ecs.ContainerImage.fromEcrRepository(this.ecrRepository, 'latest'),
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: 'api',
        logGroup,
      }),
      environment: {
        ENV: envName,
        PORT: '8000',
      },
      portMappings: [{ containerPort: 8000, hostPort: 8000 }],
      // Container-level health check; ALB target group check is separate.
      healthCheck: {
        command: [
          'CMD-SHELL',
          'curl -f http://localhost:8000/api/health || exit 1',
        ],
        interval: cdk.Duration.seconds(30),
        timeout: cdk.Duration.seconds(5),
        retries: 3,
        startPeriod: cdk.Duration.seconds(60),
      },
    });

    // ── Application Load Balancer ──────────────────────────────────────────
    this.alb = new elbv2.ApplicationLoadBalancer(this, 'AppAlb', {
      vpc: networkStack.vpc,
      internetFacing: true,
      securityGroup: networkStack.albSecurityGroup,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      loadBalancerName: `${envName}-ashta-chamma-alb`,
    });

    // HTTP → HTTPS redirect (port 80 → 443).
    this.alb.addListener('HttpListener', {
      port: 80,
      protocol: elbv2.ApplicationProtocol.HTTP,
      defaultAction: elbv2.ListenerAction.redirect({
        protocol: 'HTTPS',
        port: '443',
        permanent: true,
      }),
    });

    // ACM certificate ARN is provided as a CloudFormation parameter so the
    // template is environment-agnostic and cert provisioning can happen out-of-band.
    const certArnParam = new cdk.CfnParameter(this, 'AcmCertificateArn', {
      type: 'String',
      description: 'ARN of the ACM certificate to use for the ALB HTTPS listener',
      // Default to a placeholder so `cdk synth` succeeds without a real cert.
      default: 'arn:aws:acm:us-east-1:123456789012:certificate/00000000-0000-0000-0000-000000000000',
    });

    // HTTPS listener on port 443 — primary entry point for all traffic.
    const httpsListener = this.alb.addListener('HttpsListener', {
      port: 443,
      protocol: elbv2.ApplicationProtocol.HTTPS,
      certificates: [
        elbv2.ListenerCertificate.fromArn(certArnParam.valueAsString),
      ],
      sslPolicy: elbv2.SslPolicy.RECOMMENDED_TLS,
    });

    // ── Fargate Service ────────────────────────────────────────────────────
    this.fargateService = new ecs.FargateService(this, 'AppService', {
      cluster,
      taskDefinition,
      serviceName: `${envName}-ashta-chamma-service`,
      securityGroups: [networkStack.ecsSecurityGroup],
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      // Start with 1 task; auto-scaling handles demand.
      desiredCount: 1,
      assignPublicIp: false,
      // Circuit breaker rolls back failed deployments automatically.
      circuitBreaker: { enable: true, rollback: true },
    });

    // Register Fargate service with the HTTPS listener target group.
    httpsListener.addTargets('AppTargetGroup', {
      port: 8000,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targets: [this.fargateService],
      targetGroupName: `${envName}-api-tg`,
      // ALB health check against the FastAPI health endpoint.
      healthCheck: {
        path: '/api/health',
        interval: cdk.Duration.seconds(30),
        timeout: cdk.Duration.seconds(5),
        healthyThresholdCount: 2,
        unhealthyThresholdCount: 3,
        healthyHttpCodes: '200',
      },
      deregistrationDelay: cdk.Duration.seconds(30),
    });

    // ── Auto-Scaling ───────────────────────────────────────────────────────
    // dev: min 1, max 4 tasks; scale on CPU utilisation.
    const scalableTarget = this.fargateService.autoScaleTaskCount({
      minCapacity: 1,
      maxCapacity: 4,
    });
    scalableTarget.scaleOnCpuUtilization('CpuScaling', {
      targetUtilizationPercent: 70,
      scaleInCooldown: cdk.Duration.seconds(60),
      scaleOutCooldown: cdk.Duration.seconds(60),
    });

    // ── CloudFormation outputs ──────────────────────────────────────────────
    new cdk.CfnOutput(this, 'AlbDnsName', {
      value: this.alb.loadBalancerDnsName,
      description: 'ALB DNS name — use as backend API hostname until a custom domain is set up',
      exportName: `${envName}-AlbDnsName`,
    });
    new cdk.CfnOutput(this, 'AlbArn', {
      value: this.alb.loadBalancerArn,
      description: 'ALB ARN used by SecurityStack for WAF association',
      exportName: `${envName}-AlbArn`,
    });
    new cdk.CfnOutput(this, 'EcrRepositoryUri', {
      value: this.ecrRepository.repositoryUri,
      description: 'ECR repository URI for Docker image pushes',
      exportName: `${envName}-EcrRepositoryUri`,
    });
    new cdk.CfnOutput(this, 'EcsClusterName', {
      value: cluster.clusterName,
      description: 'ECS cluster name',
      exportName: `${envName}-EcsClusterName`,
    });
    new cdk.CfnOutput(this, 'EcsServiceName', {
      value: this.fargateService.serviceName,
      description: 'ECS service name',
      exportName: `${envName}-EcsServiceName`,
    });
  }
}
