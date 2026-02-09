# AI Agent for Real-Time Kubernetes Failure Diagnosis


Prerequisites
- Kubernetes cluster (1.19+)
- kubectl access with cluster-admin rights
- Google Gemini API key (or OpenAI API key)
- Gmail account (for email alerts, optional)
Step 1: Clone & Build
# Clone the repository
git clone <your-repo>
cd Kubernetes---AI---Agent---Service-main
# Build Docker image
docker build -t your-registry/sre-agent:latest .
# Push to your registry (ECR, Docker Hub, GCR, etc.)
docker push your-registry/sre-agent:latest
Step 2: Configure Secrets
Update deployment.yaml with your configuration:

env:
- name: OPENAI_API_KEY
  value: "your-gemini-api-key-here"
- name: ALERT_EMAIL_FROM
  value: "alerts@yourdomain.com"
- name: ALERT_EMAIL_PASS
  value: "your-gmail-app-password"  # Use App Password, not regular password
- name: ALERT_EMAIL_TO
  value: "oncall@yourdomain.com"
Security Note: In production, use Kubernetes Secrets instead of hardcoded values:

env:
- name: OPENAI_API_KEY
  valueFrom:
    secretKeyRef:
      name: ai-agent-secrets
      key: gemini-api-key
Step 3: Deploy
# Create service account and RBAC
kubectl apply -f agent-rbac.yaml
# Deploy the agent
kubectl apply -f deployment.yaml
# Verify it's running
kubectl get pods -l app=sre-ai-agent
kubectl logs -f deployment/sre-ai-agent
You should see:

🤖 SRE AI Agent Started — monitoring for crashed pods...
[2026-02-09 10:30:15] All systems nominal.
Step 4: Test with Crash Pod
# Deploy the crash test
kubectl apply -f crash-test.yaml
# Watch the agent logs
kubectl logs -f deployment/sre-ai-agent
# You should see crash detection within 30 seconds
