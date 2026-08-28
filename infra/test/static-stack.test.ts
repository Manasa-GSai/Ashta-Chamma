import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { StaticStack } from '../lib/static-stack';

/**
 * Creates a fresh StaticStack for each test.
 */
function buildStack(envName = 'test'): { stack: StaticStack; template: Template } {
  const app = new cdk.App();
  const stack = new StaticStack(app, 'TestStaticStack', { envName });
  return { stack, template: Template.fromStack(stack) };
}

describe('StaticStack', () => {
  describe('S3 Bucket', () => {
    test('creates an S3 bucket', () => {
      const { template } = buildStack();
      template.resourceCountIs('AWS::S3::Bucket', 1);
    });

    test('S3 bucket blocks all public access', () => {
      const { template } = buildStack();
      template.hasResourceProperties('AWS::S3::Bucket', {
        PublicAccessBlockConfiguration: {
          BlockPublicAcls: true,
          BlockPublicPolicy: true,
          IgnorePublicAcls: true,
          RestrictPublicBuckets: true,
        },
      });
    });

    test('S3 bucket has server-side encryption', () => {
      const { template } = buildStack();
      template.hasResourceProperties('AWS::S3::Bucket', {
        BucketEncryption: {
          ServerSideEncryptionConfiguration: expect.arrayContaining([
            expect.objectContaining({
              ServerSideEncryptionByDefault: {
                SSEAlgorithm: 'AES256',
              },
            }),
          ]),
        },
      });
    });

    test('S3 bucket policy grants OAI read access', () => {
      const { template } = buildStack();
      // OAI creates a bucket policy with a GetObject allow for the OAI.
      template.resourceCountIs('AWS::S3::BucketPolicy', 1);
    });
  });

  describe('CloudFront OAI', () => {
    test('creates an Origin Access Identity', () => {
      const { template } = buildStack();
      template.resourceCountIs('AWS::CloudFront::CloudFrontOriginAccessIdentity', 1);
    });
  });

  describe('CloudFront Distribution', () => {
    test('creates a CloudFront distribution', () => {
      const { template } = buildStack();
      template.resourceCountIs('AWS::CloudFront::Distribution', 1);
    });

    test('distribution default cache behaviour redirects HTTP to HTTPS', () => {
      const { template } = buildStack();
      template.hasResourceProperties('AWS::CloudFront::Distribution', {
        DistributionConfig: expect.objectContaining({
          DefaultCacheBehavior: expect.objectContaining({
            // redirect-to-https
            ViewerProtocolPolicy: 'redirect-to-https',
          }),
        }),
      });
    });

    test('distribution has compression enabled (gzip + brotli)', () => {
      const { template } = buildStack();
      template.hasResourceProperties('AWS::CloudFront::Distribution', {
        DistributionConfig: expect.objectContaining({
          DefaultCacheBehavior: expect.objectContaining({
            Compress: true,
          }),
        }),
      });
    });

    test('distribution enforces TLS 1.2 minimum', () => {
      const { template } = buildStack();
      template.hasResourceProperties('AWS::CloudFront::Distribution', {
        DistributionConfig: expect.objectContaining({
          ViewerCertificate: expect.objectContaining({
            MinimumProtocolVersion: 'TLSv1.2_2021',
          }),
        }),
      });
    });

    test('distribution serves index.html as default root object', () => {
      const { template } = buildStack();
      template.hasResourceProperties('AWS::CloudFront::Distribution', {
        DistributionConfig: expect.objectContaining({
          DefaultRootObject: 'index.html',
        }),
      });
    });

    test('distribution returns index.html for 403 (SPA routing)', () => {
      const { template } = buildStack();
      template.hasResourceProperties('AWS::CloudFront::Distribution', {
        DistributionConfig: expect.objectContaining({
          CustomErrorResponses: expect.arrayContaining([
            expect.objectContaining({
              ErrorCode: 403,
              ResponseCode: 200,
              ResponsePagePath: '/index.html',
            }),
          ]),
        }),
      });
    });

    test('distribution returns index.html for 404 (SPA routing)', () => {
      const { template } = buildStack();
      template.hasResourceProperties('AWS::CloudFront::Distribution', {
        DistributionConfig: expect.objectContaining({
          CustomErrorResponses: expect.arrayContaining([
            expect.objectContaining({
              ErrorCode: 404,
              ResponseCode: 200,
              ResponsePagePath: '/index.html',
            }),
          ]),
        }),
      });
    });
  });

  describe('CloudFormation Outputs', () => {
    test('exports S3 bucket name', () => {
      const { template } = buildStack();
      const outputs = template.findOutputs('BucketName');
      expect(Object.keys(outputs).length).toBeGreaterThan(0);
    });

    test('exports CloudFront domain name', () => {
      const { template } = buildStack();
      const outputs = template.findOutputs('CloudFrontDomain');
      expect(Object.keys(outputs).length).toBeGreaterThan(0);
    });

    test('exports CloudFront distribution ID', () => {
      const { template } = buildStack();
      const outputs = template.findOutputs('CloudFrontDistributionId');
      expect(Object.keys(outputs).length).toBeGreaterThan(0);
    });
  });
});
