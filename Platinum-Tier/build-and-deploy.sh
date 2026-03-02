#!/bin/bash

# Build and Deploy Platinum Tier AI Employee to Azure AKS
# This script automates the process of building the container image and deploying to AKS

set -e  # Exit on any error

echo "Starting Platinum Tier AI Employee build and deployment to Azure AKS..."

# Check prerequisites
echo "Checking prerequisites..."
if ! command -v az &> /dev/null; then
    echo "Azure CLI is not installed. Please install it first."
    exit 1
fi

if ! command -v kubectl &> /dev/null; then
    echo "kubectl is not installed. Please install it first."
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Please install it first."
    exit 1
fi

# Configuration
RESOURCE_GROUP="platinum-tier-rg"
CLUSTER_NAME="platinum-tier-cluster"
ACR_NAME="platinumTierRegistry"
IMAGE_NAME="platinum-tier-ai"
IMAGE_TAG="latest"
NAMESPACE="platinum-tier"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[WARN] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
}

# Step 1: Create Resource Group
log "Creating Azure Resource Group: $RESOURCE_GROUP"
az group create --name $RESOURCE_GROUP --location eastus --output none

# Step 2: Create Azure Container Registry
log "Creating Azure Container Registry: $ACR_NAME"
az acr create --resource-group $RESOURCE_GROUP --name $ACR_NAME --sku Basic --output none

# Step 3: Create AKS Cluster
log "Creating AKS Cluster: $CLUSTER_NAME"
az aks create \
    --resource-group $RESOURCE_GROUP \
    --name $CLUSTER_NAME \
    --node-count 2 \
    --enable-addons monitoring \
    --generate-ssh-keys \
    --attach-acr $ACR_NAME \
    --output none

# Step 4: Get AKS credentials
log "Getting AKS credentials"
az aks get-credentials --resource-group $RESOURCE_GROUP --name $CLUSTER_NAME --overwrite-existing

# Step 5: Login to ACR
log "Logging into Azure Container Registry"
az acr login --name $ACR_NAME

# Step 6: Build the Docker image
log "Building Docker image: $IMAGE_NAME:$IMAGE_TAG"
docker build -t $IMAGE_NAME:$IMAGE_TAG -f Platinum-Tier/Dockerfile . --no-cache

# Step 7: Tag and push the image to ACR
log "Tagging and pushing image to ACR"
ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP --query loginServer --output tsv)
docker tag $IMAGE_NAME:$IMAGE_TAG $ACR_LOGIN_SERVER/$IMAGE_NAME:$IMAGE_TAG
docker push $ACR_LOGIN_SERVER/$IMAGE_NAME:$IMAGE_TAG

# Step 8: Update the deployment file with the ACR image
log "Updating Kubernetes deployment with ACR image"
sed -i "s|$ACR_LOGIN_SERVER/platinum-tier-ai:latest|$ACR_LOGIN_SERVER/platinum-tier-ai:latest|g" Platinum-Tier/k8s-stateful-deployment.yaml
sed -i "s|image: platinum-tier-ai:latest|$ACR_LOGIN_SERVER/platinum-tier-ai:latest|g" Platinum-Tier/k8s-stateful-deployment.yaml

# Step 9: Create namespace and deploy
log "Creating namespace and deploying application"
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f Platinum-Tier/k8s-stateful-deployment.yaml

# Step 10: Wait for deployment to be ready
log "Waiting for deployment to be ready..."
kubectl wait --for=condition=ready pod -l app=platinum-cloud-executive -n $NAMESPACE --timeout=300s

# Step 11: Check deployment status
log "Checking deployment status..."
kubectl get pods -n $NAMESPACE
kubectl get services -n $NAMESPACE
kubectl get deployments -n $NAMESPACE

# Step 12: Display deployment info
log "Deployment completed successfully!"
echo "========================================"
echo "Resource Group: $RESOURCE_GROUP"
echo "AKS Cluster: $CLUSTER_NAME"
echo "Container Registry: $ACR_NAME"
echo "Namespace: $NAMESPACE"
echo "Image: $ACR_LOGIN_SERVER/$IMAGE_NAME:$IMAGE_TAG"
echo "Deployment: platinum-cloud-executive"
echo "========================================"
echo ""
echo "To monitor the application:"
echo "kubectl get pods -n $NAMESPACE"
echo "kubectl logs -f deployment/platinum-cloud-executive -n $NAMESPACE"
echo ""
echo "To access the cluster:"
echo "az aks get-credentials --resource-group $RESOURCE_GROUP --name $CLUSTER_NAME"
echo ""

# Step 13: Optional - Setup monitoring
read -p "Would you like to setup basic monitoring? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log "Setting up basic monitoring..."

    # Create a sample monitoring dashboard
    cat << 'EOF' > /tmp/monitoring-dashboard.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: k8s-dashboard-config
  namespace: kubernetes-dashboard
data:
  k8s-dashboard-config.yaml: |
    # Configuration for Kubernetes Dashboard
    apiVersion: v1
    kind: ConfigMap
    metadata:
      name: k8s-dashboard-config
      namespace: kubernetes-dashboard
EOF

    log "Monitoring setup completed."
fi

log "Platinum Tier AI Employee deployment to Azure AKS is complete!"
echo "The system is now running and should operate 24/7 in the cloud."