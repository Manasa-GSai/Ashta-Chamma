# Infrastructure

Infrastructure-as-code definitions for the Ashta Chamma 3D platform.

This directory will host the AWS CDK (TypeScript) stacks added by **WO-002**:

- `NetworkStack` — VPC, public/private subnets, NAT gateways, security groups
- `DatabaseStack` — RDS PostgreSQL 16 (Multi-AZ) + RDS Proxy, ElastiCache Redis
- `ComputeStack` — ECS Fargate cluster, task definition, ALB (HTTPS/WSS)
- `CdnStack` — S3 bucket for the SPA bundle + CloudFront distribution
- `MonitoringStack` — CloudWatch dashboards, alarms, X-Ray configuration

CI/CD orchestration (GitHub Actions) is tracked under **WO-003**.
