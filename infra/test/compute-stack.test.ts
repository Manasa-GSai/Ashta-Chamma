import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { NetworkStack } from '../lib/network-stack';
import { ComputeStack } from '../lib/compute-stack';

const PLACEHOLDER_SECRET_ARN =
  'arn:aws:secretsmanager:us-east-1:123456789012:secret:dev/ashtachamma/db-credentials-XXXXXX';

/**
 * Creates a NetworkStack + ComputeStack pair for each test.
 */
function buildStacks(envName = 'test'): {
  networkStack: NetworkStack;
  computeStack: ComputeStack;
  template: Template;
} {
  const app = new cdk.App();
  const networkStack = new NetworkStack(app, 'TestNetworkStack', { envName });
  const computeStack = new ComputeStack(app, 'TestComputeStack', {
    networkStack,
    dbSecretArn: PLACEHOLDER_SECRET_ARN,
    envName,
  });
  return {
    networkStack,
    computeStack,
    template: Template.fromStack(computeStack),
  };
}

describe('ComputeStack', () => {
  describe('ECR Repository', () => {
    test('creates an ECR repository', () => {
      const { template } = buildStacks();
      template.resourceCountIs('AWS::ECR::Repository', 1);
    });

    test('ECR repository has image scanning on push enabled', () => {
      const { template } = buildStacks();
      template.hasResourceProperties('AWS::ECR::Repository', {
        ImageScanningConfiguration: {
          ScanOnPush: true,
        },
      });
    });
  });

  describe('ECS Cluster and Fargate Service', () => {
    test('creates an ECS cluster', () => {
      const { template } = buildStacks();
      template.resourceCountIs('AWS::ECS::Cluster', 1);
    });

    test('cluster has container insights enabled', () => {
      const { template } = buildStacks();
      template.hasResourceProperties('AWS::ECS::Cluster', {
        ClusterSettings: expect.arrayContaining([
          expect.objectContaining({
            Name: 'containerInsights',
            Value: 'enabled',
          }),
        ]),
      });
    });

    test('creates a Fargate task definition with 0.25 vCPU (256 units)', () => {
      const { template } = buildStacks();
      template.hasResourceProperties('AWS::ECS::TaskDefinition', {
        RequiresCompatibilities: ['FARGATE'],
        Cpu: '256',
        Memory: '512',
      });
    });

    test('creates an ECS Fargate service', () => {
      const { template } = buildStacks();
      template.resourceCountIs('AWS::ECS::Service', 1);
    });

    test('Fargate service has launch type FARGATE', () => {
      const { template } = buildStacks();
      template.hasResourceProperties('AWS::ECS::Service', {
        LaunchType: 'FARGATE',
      });
    });
  });

  describe('Application Load Balancer', () => {
    test('creates an ALB', () => {
      const { template } = buildStacks();
      template.resourceCountIs('AWS::ElasticLoadBalancingV2::LoadBalancer', 1);
    });

    test('ALB is internet-facing', () => {
      const { template } = buildStacks();
      template.hasResourceProperties('AWS::ElasticLoadBalancingV2::LoadBalancer', {
        Scheme: 'internet-facing',
      });
    });

    test('creates HTTP listener on port 80', () => {
      const { template } = buildStacks();
      template.hasResourceProperties('AWS::ElasticLoadBalancingV2::Listener', {
        Port: 80,
        Protocol: 'HTTP',
      });
    });

    test('HTTP listener default action redirects to HTTPS', () => {
      const { template } = buildStacks();
      template.hasResourceProperties('AWS::ElasticLoadBalancingV2::Listener', {
        Port: 80,
        DefaultActions: expect.arrayContaining([
          expect.objectContaining({
            Type: 'redirect',
            RedirectConfig: expect.objectContaining({
              Protocol: 'HTTPS',
              Port: '443',
              StatusCode: 'HTTP_301',
            }),
          }),
        ]),
      });
    });

    test('creates HTTPS listener on port 443', () => {
      const { template } = buildStacks();
      template.hasResourceProperties('AWS::ElasticLoadBalancingV2::Listener', {
        Port: 443,
        Protocol: 'HTTPS',
      });
    });

    test('creates an ALB target group with /api/health health check', () => {
      const { template } = buildStacks();
      template.hasResourceProperties('AWS::ElasticLoadBalancingV2::TargetGroup', {
        HealthCheckPath: '/api/health',
        TargetType: 'ip',
      });
    });
  });

  describe('Auto-Scaling', () => {
    test('creates a scalable target for ECS service', () => {
      const { template } = buildStacks();
      template.resourceCountIs('AWS::ApplicationAutoScaling::ScalableTarget', 1);
    });

    test('auto-scaling min capacity is 1 and max is 4 for dev', () => {
      const { template } = buildStacks();
      template.hasResourceProperties('AWS::ApplicationAutoScaling::ScalableTarget', {
        MinCapacity: 1,
        MaxCapacity: 4,
      });
    });

    test('creates a CPU-based auto-scaling policy', () => {
      const { template } = buildStacks();
      template.hasResourceProperties(
        'AWS::ApplicationAutoScaling::ScalingPolicy',
        {
          PolicyType: 'TargetTrackingScaling',
          TargetTrackingScalingPolicyConfiguration: expect.objectContaining({
            PredefinedMetricSpecification: expect.objectContaining({
              PredefinedMetricType: 'ECSServiceAverageCPUUtilization',
            }),
          }),
        },
      );
    });
  });

  describe('IAM Roles', () => {
    test('creates a task execution role', () => {
      const { template } = buildStacks();
      // At least one IAM role with ECS task trust relationship.
      template.hasResourceProperties('AWS::IAM::Role', {
        AssumeRolePolicyDocument: {
          Statement: expect.arrayContaining([
            expect.objectContaining({
              Action: 'sts:AssumeRole',
              Principal: { Service: 'ecs-tasks.amazonaws.com' },
            }),
          ]),
        },
      });
    });
  });

  describe('CloudFormation Outputs', () => {
    test('exports ALB DNS name', () => {
      const { template } = buildStacks();
      const outputs = template.findOutputs('AlbDnsName');
      expect(Object.keys(outputs).length).toBeGreaterThan(0);
    });

    test('exports ALB ARN', () => {
      const { template } = buildStacks();
      const outputs = template.findOutputs('AlbArn');
      expect(Object.keys(outputs).length).toBeGreaterThan(0);
    });

    test('exports ECR repository URI', () => {
      const { template } = buildStacks();
      const outputs = template.findOutputs('EcrRepositoryUri');
      expect(Object.keys(outputs).length).toBeGreaterThan(0);
    });
  });
});
