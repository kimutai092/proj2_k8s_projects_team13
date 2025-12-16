# Registration App (Flask + Postgres on EKS) with ADOT

Simple online registration form built with Python/Flask and Postgres, packaged
as a Docker image and deployed to Kubernetes via Helm.

It is designed for AWS EKS clusters with worker nodes in private subnets and
uses a `LoadBalancer` Service to expose the app externally.

The application is **instrumented with OpenTelemetry** and is ready to send
traces to the **AWS Distro for OpenTelemetry (ADOT) Collector** in your EKS
cluster.

## Prerequisites

- Existing EKS cluster (kubectl & helm configured to talk to it)
- ECR repository (or any container registry)
- Docker installed locally
- Node security group allows NodePort range `30000-32767` from the NLB / internet
- ADOT Operator / add-on installed in the cluster
- An `OpenTelemetryCollector` (e.g. `adot-apm`) with an OTLP HTTP receiver
  listening on port `4318`

Example minimal collector (namespace `adot-system`):

```yaml
apiVersion: opentelemetry.io/v1alpha1
kind: OpenTelemetryCollector
metadata:
  name: adot-apm
  namespace: adot-system
spec:
  mode: deployment
  config: |
    receivers:
      otlp:
        protocols:
          grpc:
            endpoint: 0.0.0.0:4317
          http:
            endpoint: 0.0.0.0:4318

    processors:
      batch: {}

    exporters:
      awsxray: {}
      awsemf: {}

    service:
      pipelines:
        traces:
          receivers: [otlp]
          processors: [batch]
          exporters: [awsxray]
        metrics:
          receivers: [otlp]
          processors: [batch]
          exporters: [awsemf]
```

This chart assumes the collector service is reachable at:

`http://adot-apm-collector.adot-system.svc.cluster.local:4318`

You can change this with `otel.exporterEndpoint` in `values.yaml`.

## 1. Build and push Docker image

From the `app/` folder:

```bash
cd app

docker build -t registration-app:v1 .

ACCOUNT_ID=<your-account-id>
REGION=<your-region>             # e.g. us-east-2
ECR_REPO=registration-app        # or any repo name you created

docker tag registration-app:v1 $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO:v1

aws ecr get-login-password --region $REGION \
  | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO:v1
```

## 2. Deploy with Helm

From the repo root:

```bash
cd helm

helm upgrade --install registration ./registration-app \
  -n demo --create-namespace \
  --set image.repository=$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO \
  --set image.tag=v1
```

You can customize OTEL / ADOT settings via `values.yaml` under the `otel` key.

## 3. Check resources

```bash
kubectl get pods -n demo
kubectl get svc -n demo
kubectl get pvc -n demo
```

Visit the EXTERNAL-IP of the `registration-app` Service in your browser to use
the app.

Then, in AWS:

- Go to **X-Ray / ServiceLens** to view traces from the `registration-app`
- Check **CloudWatch metrics** (via ADOT EMF exporter, if configured)
