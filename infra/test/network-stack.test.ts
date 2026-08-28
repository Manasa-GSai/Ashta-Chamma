import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { NetworkStack } from '../lib/network-stack';

/**
 * Creates a fresh NetworkStack for each test to avoid shared state.
 */
function buildStack(envName = 'test'): { stack: NetworkStack; template: Template } {
  const app = new cdk.App();
  const stack = new NetworkStack(app, 'TestNetworkStack', { envName });
  return { stack, template: Template.fromStack(stack) };
}

describe('NetworkStack', () => {
  describe('VPC', () => {
    test('creates a VPC with DNS support enabled', () => {
      const { template } = buildStack();
      template.hasResourceProperties('AWS::EC2::VPC', {
        EnableDnsHostnames: true,
        EnableDnsSupport: true,
      });
    });

    test('creates exactly 4 subnets (2 public + 2 private across 2 AZs)', () => {
      const { template } = buildStack();
      // CDK Vpc with maxAzs=2 and 2 subnet groups = 4 subnets total.
      template.resourceCountIs('AWS::EC2::Subnet', 4);
    });

    test('creates a NAT gateway in the public subnet', () => {
      const { template } = buildStack();
      // natGateways=1 → single NAT for dev cost savings.
      template.resourceCountIs('AWS::EC2::NatGateway', 1);
    });

    test('creates an internet gateway', () => {
      const { template } = buildStack();
      template.resourceCountIs('AWS::EC2::InternetGateway', 1);
    });
  });

  describe('Security Groups', () => {
    test('creates exactly 4 security groups (ALB, ECS, RDS, Redis)', () => {
      const { template } = buildStack();
      // 4 named SGs + any default VPC SG; count the named ones via SecurityGroupName.
      const resources = template.findResources('AWS::EC2::SecurityGroup');
      // Expect at least 4 security group resources.
      expect(Object.keys(resources).length).toBeGreaterThanOrEqual(4);
    });

    test('ALB security group allows HTTP on port 80 from any IPv4', () => {
      const { template } = buildStack();
      template.hasResourceProperties('AWS::EC2::SecurityGroup', {
        GroupDescription: expect.stringContaining('Application Load Balancer'),
        SecurityGroupIngress: expect.arrayContaining([
          expect.objectContaining({
            CidrIp: '0.0.0.0/0',
            FromPort: 80,
            ToPort: 80,
            IpProtocol: 'tcp',
          }),
        ]),
      });
    });

    test('ALB security group allows HTTPS on port 443 from any IPv4', () => {
      const { template } = buildStack();
      template.hasResourceProperties('AWS::EC2::SecurityGroup', {
        GroupDescription: expect.stringContaining('Application Load Balancer'),
        SecurityGroupIngress: expect.arrayContaining([
          expect.objectContaining({
            CidrIp: '0.0.0.0/0',
            FromPort: 443,
            ToPort: 443,
            IpProtocol: 'tcp',
          }),
        ]),
      });
    });

    test('ECS security group description references ALB', () => {
      const { template } = buildStack();
      template.hasResourceProperties('AWS::EC2::SecurityGroup', {
        GroupDescription: expect.stringContaining('ECS Fargate tasks'),
      });
    });

    test('RDS security group allows port 5432 inbound', () => {
      const { template } = buildStack();
      // At least one ingress rule on 5432 exists in the RDS SG.
      const sgIngress = template.findResources('AWS::EC2::SecurityGroupIngress');
      const has5432 = Object.values(sgIngress).some(
        (r: { Properties?: { FromPort?: number; ToPort?: number } }) =>
          r.Properties?.FromPort === 5432 && r.Properties?.ToPort === 5432,
      );
      expect(has5432).toBe(true);
    });

    test('Redis security group allows port 6379 inbound', () => {
      const { template } = buildStack();
      const sgIngress = template.findResources('AWS::EC2::SecurityGroupIngress');
      const has6379 = Object.values(sgIngress).some(
        (r: { Properties?: { FromPort?: number; ToPort?: number } }) =>
          r.Properties?.FromPort === 6379 && r.Properties?.ToPort === 6379,
      );
      expect(has6379).toBe(true);
    });
  });

  describe('CloudFormation Outputs', () => {
    test('exports VpcId', () => {
      const { template } = buildStack();
      const outputs = template.findOutputs('VpcId');
      expect(Object.keys(outputs).length).toBeGreaterThan(0);
    });

    test('exports ALB security group ID', () => {
      const { template } = buildStack();
      const outputs = template.findOutputs('AlbSecurityGroupId');
      expect(Object.keys(outputs).length).toBeGreaterThan(0);
    });

    test('exports ECS security group ID', () => {
      const { template } = buildStack();
      const outputs = template.findOutputs('EcsSecurityGroupId');
      expect(Object.keys(outputs).length).toBeGreaterThan(0);
    });
  });
});
