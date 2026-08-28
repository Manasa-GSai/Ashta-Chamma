import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { SecurityStack } from '../lib/security-stack';

const PLACEHOLDER_ALB_ARN =
  'arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/dev-ashta-chamma-alb/0123456789abcdef';

/**
 * Creates a fresh SecurityStack for each test using a placeholder ALB ARN
 * to avoid a dependency on ComputeStack during unit tests.
 */
function buildStack(envName = 'test'): { stack: SecurityStack; template: Template } {
  const app = new cdk.App();
  const stack = new SecurityStack(app, 'TestSecurityStack', {
    albArn: PLACEHOLDER_ALB_ARN,
    envName,
  });
  return { stack, template: Template.fromStack(stack) };
}

describe('SecurityStack', () => {
  describe('WAF WebACL', () => {
    test('creates a WAF WebACL', () => {
      const { template } = buildStack();
      template.resourceCountIs('AWS::WAFv2::WebACL', 1);
    });

    test('WAF scope is REGIONAL (for ALB association)', () => {
      const { template } = buildStack();
      template.hasResourceProperties('AWS::WAFv2::WebACL', {
        Scope: 'REGIONAL',
      });
    });

    test('WAF default action is ALLOW', () => {
      const { template } = buildStack();
      template.hasResourceProperties('AWS::WAFv2::WebACL', {
        DefaultAction: { Allow: {} },
      });
    });

    test('WAF has a rate-limit rule at priority 1', () => {
      const { template } = buildStack();
      template.hasResourceProperties('AWS::WAFv2::WebACL', {
        Rules: expect.arrayContaining([
          expect.objectContaining({
            Priority: 1,
            Statement: expect.objectContaining({
              RateBasedStatement: expect.objectContaining({
                Limit: 1000,
                AggregateKeyType: 'IP',
              }),
            }),
          }),
        ]),
      });
    });

    test('rate-limit rule action is BLOCK', () => {
      const { template } = buildStack();
      template.hasResourceProperties('AWS::WAFv2::WebACL', {
        Rules: expect.arrayContaining([
          expect.objectContaining({
            Priority: 1,
            Action: { Block: {} },
          }),
        ]),
      });
    });

    test('WAF includes AWS managed common rule set', () => {
      const { template } = buildStack();
      template.hasResourceProperties('AWS::WAFv2::WebACL', {
        Rules: expect.arrayContaining([
          expect.objectContaining({
            Statement: expect.objectContaining({
              ManagedRuleGroupStatement: expect.objectContaining({
                Name: 'AWSManagedRulesCommonRuleSet',
                VendorName: 'AWS',
              }),
            }),
          }),
        ]),
      });
    });
  });

  describe('WAF ALB Association', () => {
    test('creates a WAF WebACL association for the ALB', () => {
      const { template } = buildStack();
      template.resourceCountIs('AWS::WAFv2::WebACLAssociation', 1);
    });

    test('WAF association references the provided ALB ARN', () => {
      const { template } = buildStack();
      template.hasResourceProperties('AWS::WAFv2::WebACLAssociation', {
        ResourceArn: PLACEHOLDER_ALB_ARN,
      });
    });
  });

  describe('Secrets Manager', () => {
    test('creates 3 Secrets Manager secrets (Clerk publishable, Clerk secret, Redis auth)', () => {
      const { template } = buildStack();
      template.resourceCountIs('AWS::SecretsManager::Secret', 3);
    });

    test('creates a secret for the Clerk publishable key', () => {
      const { template } = buildStack();
      template.hasResourceProperties('AWS::SecretsManager::Secret', {
        Description: expect.stringContaining('Clerk publishable API key'),
      });
    });

    test('creates a secret for the Clerk secret key', () => {
      const { template } = buildStack();
      template.hasResourceProperties('AWS::SecretsManager::Secret', {
        Description: expect.stringContaining('Clerk secret API key'),
      });
    });

    test('creates a secret for the Redis auth token', () => {
      const { template } = buildStack();
      template.hasResourceProperties('AWS::SecretsManager::Secret', {
        Description: expect.stringContaining('Redis AUTH token'),
      });
    });
  });

  describe('CloudFormation Outputs', () => {
    test('exports WAF WebACL ARN', () => {
      const { template } = buildStack();
      const outputs = template.findOutputs('WafWebAclArn');
      expect(Object.keys(outputs).length).toBeGreaterThan(0);
    });

    test('exports Clerk publishable key secret ARN', () => {
      const { template } = buildStack();
      const outputs = template.findOutputs('ClerkPublishableKeySecretArn');
      expect(Object.keys(outputs).length).toBeGreaterThan(0);
    });

    test('exports Clerk secret key secret ARN', () => {
      const { template } = buildStack();
      const outputs = template.findOutputs('ClerkSecretKeySecretArn');
      expect(Object.keys(outputs).length).toBeGreaterThan(0);
    });

    test('exports Redis auth token secret ARN', () => {
      const { template } = buildStack();
      const outputs = template.findOutputs('RedisAuthTokenSecretArn');
      expect(Object.keys(outputs).length).toBeGreaterThan(0);
    });
  });
});
