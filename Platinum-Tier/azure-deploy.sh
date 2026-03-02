# Azure AKS Deployment for Platinum Tier AI Employee
# This script assumes you have Azure CLI and kubectl installed and configured

# 1. Create Resource Group
az group create --name platinum-tier-rg --location eastus

# 2. Create AKS Cluster
az aks create \
  --resource-group platinum-tier-rg \
  --name platinum-tier-cluster \
  --node-count 2 \
  --enable-addons monitoring \
  --generate-ssh-keys

# 3. Get AKS credentials
az aks get-credentials --resource-group platinum-tier-rg --name platinum-tier-cluster

# 4. Create the namespace and deploy the application
kubectl apply -f k8s-stateful-deployment.yaml

# 5. Build and push the Docker image to Azure Container Registry (if needed)
# First, create ACR
az acr create --resource-group platinum-tier-rg --name platinumTierRegistry --sku Basic

# Login to ACR
az acr login --name platinumTierRegistry

# Tag the image
docker build -t platinum-tier-ai:latest ./Platinum-Tier/ --file ./Platinum-Tier/Dockerfile
docker tag platinum-tier-ai:latest platinumtierregistry.azurecr.io/platinum-tier-ai:latest

# Push the image
docker push platinumtierregistry.azurecr.io/platinum-tier-ai:latest

# Update the k8s-stateful-deployment.yaml to use the ACR image:
# Replace:
#   image: platinum-tier-ai:latest
# With:
#   image: platinumtierregistry.azurecr.io/platinum-tier-ai:latest

# Then apply the updated deployment
kubectl apply -f k8s-stateful-deployment.yaml

# 6. Monitor the deployment
kubectl get pods -n platinum-tier
kubectl get services -n platinum-tier

# 7. To check logs
kubectl logs -n platinum-tier deployment/platinum-cloud-executive

# 8. Create an ingress controller (optional, for external access)
# Add the ingress-nginx repository
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

# Use Helm to deploy an ingress controller
helm install nginx-ingress ingress-nginx/ingress-nginx \
    --namespace platinum-tier \
    --set controller.replicaCount=1 \
    --set controller.nodeSelector."kubernetes\.io/os"=linux \
    --set defaultBackend.nodeSelector."kubernetes\.io/os"=linux

# 9. Scale up if needed (for redundancy)
kubectl scale deployment platinum-cloud-executive --replicas=2 -n platinum-tier

# 10. To delete the resources when no longer needed
# az group delete --name platinum-tier-rg --yes --no-wait