# nginx-demo

Simple NGINX Deployment exposed via a Kubernetes `LoadBalancer` Service.

## Deploy

```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

kubectl get svc nginx-demo-lb
```

Use the `EXTERNAL-IP` from the Service to access NGINX in your browser.
```
