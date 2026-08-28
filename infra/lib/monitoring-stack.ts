/**
 * MonitoringStack — CloudWatch Log Groups, Alarms, and Operational Dashboard.
 *
 * This stack satisfies WO-035 acceptance criteria:
 *  1. ECS task logs → CloudWatch Log Group (30-day retention)
 *  2. Custom metrics: api_response_time_ms, ws_message_latency_ms,
 *     active_rooms_count, connected_players_count
 *  3-6. Alarms for API latency SLO, error-rate SLO, ECS task count, WS latency SLO
 *  7. Dashboard: latency (p50/p95/p99), error rate, rooms, players, ECS task/CPU/memory
 *  8. All alarms publish to an SNS topic (configurable email / Slack)
 *
 * Cost constraints:
 *  - All metrics use 60-second (standard) resolution — NOT high-resolution
 *  - Alarm evaluation periods are 5 minutes to reduce noise / alert fatigue
 *  - Namespaces used: AshtaChamma/API, AshtaChamma/WebSocket, AshtaChamma/Game
 */

import * as cdk from 'aws-cdk-lib';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as cloudwatchActions from 'aws-cdk-lib/aws-cloudwatch-actions';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as snsSubscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import { Construct } from 'constructs';

// ──────────────────────────────────────────────────────────────────────────────
// Constants
// ──────────────────────────────────────────────────────────────────────────────

const API_NAMESPACE = 'AshtaChamma/API';
const WS_NAMESPACE = 'AshtaChamma/WebSocket';
const GAME_NAMESPACE = 'AshtaChamma/Game';

/**
 * Evaluation period for all SLO alarms: 5 minutes.
 * A single 5-minute period satisfies "5 consecutive minutes" when
 * evaluationPeriods=1 and the metric Period is also 5 minutes.
 */
const SLO_PERIOD = cdk.Duration.minutes(5);

// ──────────────────────────────────────────────────────────────────────────────
// Props
// ──────────────────────────────────────────────────────────────────────────────

export interface MonitoringStackProps extends cdk.StackProps {
  /** Name of the ECS service for ECS CloudWatch metrics dimensions. */
  readonly ecsServiceName: string;
  /** Name of the ECS cluster for ECS CloudWatch metrics dimensions. */
  readonly ecsClusterName: string;
  /**
   * Optional email address to subscribe to the alarm SNS topic.
   * Additional subscriptions (Slack, PagerDuty) can be added post-deploy.
   */
  readonly alarmEmailAddress?: string;
}

// ──────────────────────────────────────────────────────────────────────────────
// Stack
// ──────────────────────────────────────────────────────────────────────────────

export class MonitoringStack extends cdk.Stack {
  /** SNS topic that receives all CloudWatch alarm state-change notifications. */
  public readonly alarmTopic: sns.Topic;
  /** CloudWatch Log Group for ECS API task stdout/stderr (30-day retention). */
  public readonly apiLogGroup: logs.LogGroup;
  /** CloudWatch operational dashboard. */
  public readonly dashboard: cloudwatch.Dashboard;

  constructor(scope: Construct, id: string, props: MonitoringStackProps) {
    super(scope, id, props);

    // ── SNS alarm topic ───────────────────────────────────────────────────────
    this.alarmTopic = new sns.Topic(this, 'AlarmTopic', {
      topicName: 'AshtaChamma-Alarms',
      displayName: 'Ashta Chamma CloudWatch Alarms',
    });

    if (props.alarmEmailAddress) {
      this.alarmTopic.addSubscription(
        new snsSubscriptions.EmailSubscription(props.alarmEmailAddress),
      );
    }

    // ── Log Group ─────────────────────────────────────────────────────────────
    // ECS tasks are configured to use the awslogs driver with this log group.
    // 30-day retention satisfies the minimum for operational debugging (AC-1).
    this.apiLogGroup = new logs.LogGroup(this, 'ApiLogGroup', {
      logGroupName: '/ecs/ashta-chamma-api',
      retention: logs.RetentionDays.ONE_MONTH, // 30 days
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // ── Metric definitions ─────────────────────────────────────────────────────

    // AC-2: api_response_time_ms
    const apiLatencyP95 = new cloudwatch.Metric({
      namespace: API_NAMESPACE,
      metricName: 'api_response_time_ms',
      statistic: cloudwatch.Stats.percentile(95),
      period: SLO_PERIOD,
      label: 'API Latency p95 (ms)',
    });

    const apiLatencyP50 = new cloudwatch.Metric({
      namespace: API_NAMESPACE,
      metricName: 'api_response_time_ms',
      statistic: cloudwatch.Stats.percentile(50),
      period: SLO_PERIOD,
      label: 'API Latency p50 (ms)',
    });

    const apiLatencyP99 = new cloudwatch.Metric({
      namespace: API_NAMESPACE,
      metricName: 'api_response_time_ms',
      statistic: cloudwatch.Stats.percentile(99),
      period: SLO_PERIOD,
      label: 'API Latency p99 (ms)',
    });

    // AC-2: ws_message_latency_ms
    const wsLatencyP95 = new cloudwatch.Metric({
      namespace: WS_NAMESPACE,
      metricName: 'ws_message_latency_ms',
      statistic: cloudwatch.Stats.percentile(95),
      period: SLO_PERIOD,
      label: 'WS Latency p95 (ms)',
    });

    // AC-2: active_rooms_count
    const activeRoomsMetric = new cloudwatch.Metric({
      namespace: GAME_NAMESPACE,
      metricName: 'active_rooms_count',
      statistic: cloudwatch.Stats.AVERAGE,
      period: SLO_PERIOD,
      label: 'Active Rooms',
    });

    // AC-2: connected_players_count
    const connectedPlayersMetric = new cloudwatch.Metric({
      namespace: GAME_NAMESPACE,
      metricName: 'connected_players_count',
      statistic: cloudwatch.Stats.AVERAGE,
      period: SLO_PERIOD,
      label: 'Connected Players',
    });

    // AC-4: error rate = (5xx / total) * 100
    // IF guard prevents division by zero when there are no requests.
    const errorRateMetric = new cloudwatch.MathExpression({
      expression: 'IF(total > 0, (errors / total) * 100, 0)',
      label: 'Error Rate (%)',
      period: SLO_PERIOD,
      usingMetrics: {
        errors: new cloudwatch.Metric({
          namespace: API_NAMESPACE,
          metricName: 'http_5xx_count',
          statistic: cloudwatch.Stats.SUM,
          period: SLO_PERIOD,
        }),
        total: new cloudwatch.Metric({
          namespace: API_NAMESPACE,
          metricName: 'http_request_count',
          statistic: cloudwatch.Stats.SUM,
          period: SLO_PERIOD,
        }),
      },
    });

    // ECS built-in metrics (AWS/ECS namespace)
    const ecsTaskCountMetric = new cloudwatch.Metric({
      namespace: 'AWS/ECS',
      metricName: 'RunningTaskCount',
      dimensionsMap: {
        ServiceName: props.ecsServiceName,
        ClusterName: props.ecsClusterName,
      },
      statistic: cloudwatch.Stats.MINIMUM,
      period: cdk.Duration.minutes(1),
      label: 'ECS Running Tasks',
    });

    const ecsCpuMetric = new cloudwatch.Metric({
      namespace: 'AWS/ECS',
      metricName: 'CPUUtilization',
      dimensionsMap: {
        ServiceName: props.ecsServiceName,
        ClusterName: props.ecsClusterName,
      },
      statistic: cloudwatch.Stats.AVERAGE,
      period: SLO_PERIOD,
      label: 'CPU Utilization (%)',
    });

    const ecsMemoryMetric = new cloudwatch.Metric({
      namespace: 'AWS/ECS',
      metricName: 'MemoryUtilization',
      dimensionsMap: {
        ServiceName: props.ecsServiceName,
        ClusterName: props.ecsClusterName,
      },
      statistic: cloudwatch.Stats.AVERAGE,
      period: SLO_PERIOD,
      label: 'Memory Utilization (%)',
    });

    // ── Alarms ────────────────────────────────────────────────────────────────

    // AC-3: API p95 latency > 200ms SLO — 1 evaluation period × 5 min = 5 min
    const apiLatencyAlarm = new cloudwatch.Alarm(this, 'ApiLatencyAlarm', {
      alarmName: 'AshtaChamma-API-Latency-p95',
      alarmDescription:
        'API p95 response time exceeds the 200ms SLO for 5 consecutive minutes.',
      metric: apiLatencyP95,
      threshold: 200,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });
    apiLatencyAlarm.addAlarmAction(new cloudwatchActions.SnsAction(this.alarmTopic));
    apiLatencyAlarm.addOkAction(new cloudwatchActions.SnsAction(this.alarmTopic));

    // AC-4: Error rate > 1% — 1 evaluation period × 5 min = 5 min
    const errorRateAlarm = new cloudwatch.Alarm(this, 'ErrorRateAlarm', {
      alarmName: 'AshtaChamma-API-ErrorRate',
      alarmDescription:
        'HTTP 5xx error rate exceeds the 1% SLO for 5 consecutive minutes.',
      metric: errorRateMetric,
      threshold: 1,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });
    errorRateAlarm.addAlarmAction(new cloudwatchActions.SnsAction(this.alarmTopic));
    errorRateAlarm.addOkAction(new cloudwatchActions.SnsAction(this.alarmTopic));

    // AC-5: ECS task count drops to 0 — service is completely down; treat missing
    // data as BREACHING because if ECS stops reporting, the service is likely gone.
    const ecsTaskAlarm = new cloudwatch.Alarm(this, 'EcsTaskCountAlarm', {
      alarmName: 'AshtaChamma-ECS-NoRunningTasks',
      alarmDescription:
        'ECS running task count dropped to 0 — the API service is completely unavailable.',
      metric: ecsTaskCountMetric,
      threshold: 1,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.BREACHING,
    });
    ecsTaskAlarm.addAlarmAction(new cloudwatchActions.SnsAction(this.alarmTopic));
    ecsTaskAlarm.addOkAction(new cloudwatchActions.SnsAction(this.alarmTopic));

    // AC-6: WebSocket p95 latency > 100ms SLO — 1 evaluation period × 5 min
    const wsLatencyAlarm = new cloudwatch.Alarm(this, 'WsLatencyAlarm', {
      alarmName: 'AshtaChamma-WS-Latency-p95',
      alarmDescription:
        'WebSocket message p95 latency exceeds the 100ms SLO for 5 consecutive minutes.',
      metric: wsLatencyP95,
      threshold: 100,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });
    wsLatencyAlarm.addAlarmAction(new cloudwatchActions.SnsAction(this.alarmTopic));
    wsLatencyAlarm.addOkAction(new cloudwatchActions.SnsAction(this.alarmTopic));

    // ── Dashboard (AC-7) ──────────────────────────────────────────────────────
    this.dashboard = new cloudwatch.Dashboard(this, 'OperationalDashboard', {
      dashboardName: 'AshtaChamma-Operations',
    });

    // Row 1: API latency (p50 / p95 / p99) and error rate
    this.dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: 'API Response Time (ms)',
        left: [apiLatencyP50, apiLatencyP95, apiLatencyP99],
        leftAnnotations: [
          { value: 200, label: 'SLO: 200ms (p95)', color: '#ff0000' },
        ],
        width: 12,
        height: 6,
      }),
      new cloudwatch.GraphWidget({
        title: 'Error Rate (%)',
        left: [errorRateMetric],
        leftAnnotations: [
          { value: 1, label: 'SLO: 1%', color: '#ff0000' },
        ],
        width: 12,
        height: 6,
      }),
    );

    // Row 2: Game metrics and WebSocket latency
    this.dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: 'Active Rooms',
        left: [activeRoomsMetric],
        width: 8,
        height: 6,
      }),
      new cloudwatch.GraphWidget({
        title: 'Connected Players',
        left: [connectedPlayersMetric],
        width: 8,
        height: 6,
      }),
      new cloudwatch.GraphWidget({
        title: 'WebSocket Message Latency (ms)',
        left: [wsLatencyP95],
        leftAnnotations: [
          { value: 100, label: 'SLO: 100ms (p95)', color: '#ff0000' },
        ],
        width: 8,
        height: 6,
      }),
    );

    // Row 3: ECS infrastructure health
    this.dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: 'ECS Running Task Count',
        left: [ecsTaskCountMetric],
        leftAnnotations: [
          { value: 1, label: 'Min healthy: 1', color: '#ff0000' },
        ],
        width: 8,
        height: 6,
      }),
      new cloudwatch.GraphWidget({
        title: 'ECS CPU Utilization (%)',
        left: [ecsCpuMetric],
        leftAnnotations: [
          { value: 70, label: 'Scale-out trigger: 70%', color: '#ffaa00' },
        ],
        width: 8,
        height: 6,
      }),
      new cloudwatch.GraphWidget({
        title: 'ECS Memory Utilization (%)',
        left: [ecsMemoryMetric],
        width: 8,
        height: 6,
      }),
    );

    // ── Outputs ───────────────────────────────────────────────────────────────

    new cdk.CfnOutput(this, 'AlarmTopicArn', {
      value: this.alarmTopic.topicArn,
      description: 'SNS topic ARN for CloudWatch alarm notifications',
      exportName: 'AshtaChamma-AlarmTopicArn',
    });

    new cdk.CfnOutput(this, 'ApiLogGroupName', {
      value: this.apiLogGroup.logGroupName,
      description: 'CloudWatch Log Group for ECS API task logs',
      exportName: 'AshtaChamma-ApiLogGroupName',
    });

    new cdk.CfnOutput(this, 'DashboardUrl', {
      value: `https://${this.region}.console.aws.amazon.com/cloudwatch/home#dashboards:name=AshtaChamma-Operations`,
      description: 'CloudWatch Dashboard URL',
    });
  }
}
