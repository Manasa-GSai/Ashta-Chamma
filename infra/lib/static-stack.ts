import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import { Construct } from 'constructs';

export interface StaticStackProps extends cdk.StackProps {
  /** Logical environment name used for resource naming and CFN exports. */
  envName?: string;
}

/**
 * StaticStack provisions the CDN layer for the React SPA:
 * - Private S3 bucket (no public access) as the asset origin
 * - CloudFront Origin Access Identity (OAI) for bucket access
 * - CloudFront distribution with HTTPS-only policy, gzip/brotli compression,
 *   and TLS 1.2+ minimum protocol version
 */
export class StaticStack extends cdk.Stack {
  public readonly bucket: s3.Bucket;
  public readonly distribution: cloudfront.Distribution;

  constructor(scope: Construct, id: string, props?: StaticStackProps) {
    super(scope, id, props);

    const envName = props?.envName ?? 'dev';

    // ── S3 Bucket ──────────────────────────────────────────────────────────
    // All public access blocked; only CloudFront OAI can read objects.
    this.bucket = new s3.Bucket(this, 'StaticBucket', {
      bucketName: `${envName}-ashta-chamma-static-${cdk.Aws.ACCOUNT_ID}`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      versioned: false,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      enforceSSL: true,
    });

    // ── CloudFront OAI ─────────────────────────────────────────────────────
    // OAI restricts direct S3 access; all asset requests must go through CloudFront.
    const oai = new cloudfront.OriginAccessIdentity(this, 'StaticOAI', {
      comment: `OAI for ${envName} Ashta Chamma static assets`,
    });
    this.bucket.grantRead(oai);

    // ── CloudFront Distribution ────────────────────────────────────────────
    this.distribution = new cloudfront.Distribution(this, 'StaticDistribution', {
      comment: `${envName} Ashta Chamma SPA CDN`,
      defaultRootObject: 'index.html',
      // Minimum TLS 1.2 enforced across all viewer connections.
      minimumProtocolVersion: cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
      defaultBehavior: {
        origin: new origins.S3Origin(this.bucket, { originAccessIdentity: oai }),
        // Redirect all HTTP requests to HTTPS.
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        // gzip and brotli compression enabled automatically via this flag.
        compress: true,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
        cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
        originRequestPolicy: cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN,
      },
      // SPA routing: any path not found returns index.html with 200 so
      // the React router handles the URL client-side.
      errorResponses: [
        {
          httpStatus: 403,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.seconds(0),
        },
        {
          httpStatus: 404,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.seconds(0),
        },
      ],
      priceClass: cloudfront.PriceClass.PRICE_CLASS_100,
    });

    // ── CloudFormation outputs ──────────────────────────────────────────────
    new cdk.CfnOutput(this, 'BucketName', {
      value: this.bucket.bucketName,
      description: 'S3 bucket name for SPA build artifact uploads',
      exportName: `${envName}-StaticBucketName`,
    });
    new cdk.CfnOutput(this, 'CloudFrontDomain', {
      value: this.distribution.distributionDomainName,
      description: 'CloudFront distribution domain name',
      exportName: `${envName}-CloudFrontDomain`,
    });
    new cdk.CfnOutput(this, 'CloudFrontDistributionId', {
      value: this.distribution.distributionId,
      description: 'CloudFront distribution ID — used for cache invalidations',
      exportName: `${envName}-CloudFrontDistributionId`,
    });
  }
}
