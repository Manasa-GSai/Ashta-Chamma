#!/usr/bin/env node
/**
 * CDK App entry point for Ashta Chamma 3D infrastructure.
 *
 * Stack hierarchy (each stack depends on the one above it):
 *   NetworkStack → DatabaseStack → ComputeStack → SecurityStack
 *   StaticStack (independent of compute)
 *
 * Usage:
 *   cdk synth
 *   cdk deploy --all -c envName=staging
 *   cdk deploy dev-NetworkStack dev-DatabaseStack
 */
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { NetworkStack } from '../lib/network-stack';
import { DatabaseStack } from '../lib/database-stack';
import { ComputeStack } from '../lib/compute-stack';
import { StaticStack } from '../lib/static-stack';
import { SecurityStack } from '../lib/security-stack';

const app = new cdk.App();

// Resolve environment — allows deploying to multiple AWS accounts/regions.
const env: cdk.Environment = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION ?? 'us-east-1',
};

// Environment name context value: `cdk deploy -c envName=staging`
const envName: string = (app.node.tryGetContext('envName') as string | undefined) ?? 'dev';

// ── NetworkStack ────────────────────────────────────────────────────────────
const networkStack = new NetworkStack(app, `${envName}-NetworkStack`, {
  env,
  envName,
  description: 'VPC, subnets, NAT gateway, and security groups for Ashta Chamma 3D',
});

// ── DatabaseStack ───────────────────────────────────────────────────────────
const databaseStack = new DatabaseStack(app, `${envName}-DatabaseStack`, {
  env,
  networkStack,
  envName,
  description: 'RDS PostgreSQL 16, RDS Proxy, and ElastiCache Redis for Ashta Chamma 3D',
});
databaseStack.addDependency(networkStack);

// ── ComputeStack ────────────────────────────────────────────────────────────
const computeStack = new ComputeStack(app, `${envName}-ComputeStack`, {
  env,
  networkStack,
  dbSecretArn: databaseStack.dbSecret.secretArn,
  envName,
  description: 'ECS Fargate cluster, ALB, and ECR repository for Ashta Chamma 3D',
});
computeStack.addDependency(databaseStack);

// ── StaticStack ─────────────────────────────────────────────────────────────
// Deployed independently — does not depend on compute or database resources.
const staticStack = new StaticStack(app, `${envName}-StaticStack`, {
  env,
  envName,
  description: 'S3 bucket and CloudFront distribution for Ashta Chamma 3D SPA assets',
});

// ── SecurityStack ───────────────────────────────────────────────────────────
const securityStack = new SecurityStack(app, `${envName}-SecurityStack`, {
  env,
  albArn: computeStack.alb.loadBalancerArn,
  envName,
  description: 'WAF WebACL, rate limiting, and Secrets Manager entries for Ashta Chamma 3D',
});
securityStack.addDependency(computeStack);

// Suppress unused variable warnings — stacks are registered with the CDK app
// via their constructors; explicit references are only required for cross-stack props.
void staticStack;
