import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { NetworkStack } from '../lib/network-stack';
import { DatabaseStack } from '../lib/database-stack';

/**
 * Creates a minimal NetworkStack + DatabaseStack pair for each test.
 */
function buildStacks(envName = 'test'): {
  networkStack: NetworkStack;
  databaseStack: DatabaseStack;
  template: Template;
} {
  const app = new cdk.App();
  const networkStack = new NetworkStack(app, 'TestNetworkStack', { envName });
  const databaseStack = new DatabaseStack(app, 'TestDatabaseStack', {
    networkStack,
    envName,
  });
  return {
    networkStack,
    databaseStack,
    template: Template.fromStack(databaseStack),
  };
}

describe('DatabaseStack', () => {
  describe('RDS PostgreSQL 16', () => {
    test('creates an RDS instance with PostgreSQL 16 engine', () => {
      const { template } = buildStacks();
      template.hasResourceProperties('AWS::RDS::DBInstance', {
        Engine: 'postgres',
        EngineVersion: expect.stringMatching(/^16/),
      });
    });

    test('uses db.t3.micro instance type for Phase-1 cost target', () => {
      const { template } = buildStacks();
      template.hasResourceProperties('AWS::RDS::DBInstance', {
        DBInstanceClass: 'db.t3.micro',
      });
    });

    test('has storage encryption enabled', () => {
      const { template } = buildStacks();
      template.hasResourceProperties('AWS::RDS::DBInstance', {
        StorageEncrypted: true,
      });
    });

    test('is NOT publicly accessible', () => {
      const { template } = buildStacks();
      template.hasResourceProperties('AWS::RDS::DBInstance', {
        PubliclyAccessible: false,
      });
    });

    test('multi-AZ is disabled for dev cost savings', () => {
      const { template } = buildStacks();
      template.hasResourceProperties('AWS::RDS::DBInstance', {
        MultiAZ: false,
      });
    });

    test('auto-generates a Secrets Manager credential', () => {
      const { template } = buildStacks();
      // fromGeneratedSecret creates a Secret resource linked to the DB instance.
      template.resourceCountIs('AWS::SecretsManager::Secret', 1);
    });

    test('database name is set to ashtachamma', () => {
      const { template } = buildStacks();
      template.hasResourceProperties('AWS::RDS::DBInstance', {
        DBName: 'ashtachamma',
      });
    });
  });

  describe('RDS Proxy', () => {
    test('creates an RDS Proxy', () => {
      const { template } = buildStacks();
      template.resourceCountIs('AWS::RDS::DBProxy', 1);
    });

    test('RDS Proxy requires TLS', () => {
      const { template } = buildStacks();
      template.hasResourceProperties('AWS::RDS::DBProxy', {
        RequireTLS: true,
      });
    });

    test('RDS Proxy engine family is POSTGRESQL', () => {
      const { template } = buildStacks();
      template.hasResourceProperties('AWS::RDS::DBProxy', {
        EngineFamily: 'POSTGRESQL',
      });
    });
  });

  describe('ElastiCache Redis', () => {
    test('creates an ElastiCache cluster with Redis engine', () => {
      const { template } = buildStacks();
      template.hasResourceProperties('AWS::ElastiCache::CacheCluster', {
        Engine: 'redis',
      });
    });

    test('uses cache.t3.micro node type for Phase-1 cost target', () => {
      const { template } = buildStacks();
      template.hasResourceProperties('AWS::ElastiCache::CacheCluster', {
        CacheNodeType: 'cache.t3.micro',
      });
    });

    test('has in-transit encryption enabled', () => {
      const { template } = buildStacks();
      template.hasResourceProperties('AWS::ElastiCache::CacheCluster', {
        TransitEncryptionEnabled: true,
      });
    });

    test('has exactly 1 cache node for dev cost savings', () => {
      const { template } = buildStacks();
      template.hasResourceProperties('AWS::ElastiCache::CacheCluster', {
        NumCacheNodes: 1,
      });
    });

    test('creates an ElastiCache subnet group for private subnets', () => {
      const { template } = buildStacks();
      template.resourceCountIs('AWS::ElastiCache::SubnetGroup', 1);
    });
  });

  describe('CloudFormation Outputs', () => {
    test('exports DB proxy endpoint', () => {
      const { template } = buildStacks();
      const outputs = template.findOutputs('DbProxyEndpoint');
      expect(Object.keys(outputs).length).toBeGreaterThan(0);
    });

    test('exports Redis endpoint', () => {
      const { template } = buildStacks();
      const outputs = template.findOutputs('RedisEndpoint');
      expect(Object.keys(outputs).length).toBeGreaterThan(0);
    });

    test('exports DB secret ARN', () => {
      const { template } = buildStacks();
      const outputs = template.findOutputs('DbSecretArn');
      expect(Object.keys(outputs).length).toBeGreaterThan(0);
    });
  });
});
