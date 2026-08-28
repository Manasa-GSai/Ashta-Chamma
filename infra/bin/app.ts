#!/usr/bin/env node
/**
 * CDK application entry point for Ashta Chamma 3D infrastructure.
 *
 * Instantiates and composes all CDK stacks.  The MonitoringStack depends on
 * ECS service/cluster names from ComputeStack — passed via props to keep
 * stacks decoupled at the CDK level.
 */
import * as cdk from 'aws-cdk-lib';
import { MonitoringStack } from '../lib/monitoring-stack';

const app = new cdk.App();

// Environment configuration — override via CDK context or env vars in CI/CD
const env: cdk.Environment = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION ?? 'us-east-1',
};

// ECS service and cluster names are injected from ComputeStack outputs.
// For MVP these are hard-coded; a future refactor can use cross-stack references.
const ecsServiceName = app.node.tryGetContext('ecsServiceName') ?? 'ashta-chamma-service';
const ecsClusterName = app.node.tryGetContext('ecsClusterName') ?? 'ashta-chamma-cluster';
const alarmEmailAddress = app.node.tryGetContext('alarmEmailAddress') as string | undefined;

new MonitoringStack(app, 'AshtaChammaMonitoringStack', {
  env,
  ecsServiceName,
  ecsClusterName,
  alarmEmailAddress,
  description: 'CloudWatch metrics, alarms, and dashboards for Ashta Chamma 3D',
  tags: {
    Project: 'AshtaChamma',
    Component: 'Monitoring',
  },
});

app.synth();
