import pandas as pd 
import re   
import time
import json
from collections import Counter
import boto3
from moto import mock_aws
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Global mock reference
mock_env = None
BUCKET_NAME = 'cloud-shield-logs-bucket'
LOG_KEY = 'raw_logs/server.log'

# Global Auto-scaling states
scaled_instances = []
auto_scaling_triggered = False

def setup_mock_s3():
    """Starts mock S3, creates the virtual bucket, and uploads the local server.log"""
    print("[*] Initializing Virtual AWS S3 environment...")
    mock = mock_aws()
    mock.start()
    
    s3_client = boto3.client('s3', region_name='us-east-1')
    s3_client.create_bucket(Bucket=BUCKET_NAME)
    
    # Upload local log file to our mock bucket (in same directory backend/)
    print(f"[#] Uploading 'server.log' to S3 bucket '{BUCKET_NAME}'...")
    s3_client.upload_file('server.log', BUCKET_NAME, LOG_KEY)
    return mock

def generate_edge_rules(df_client):
    """Generates edge caching recommendations in edge_rules.json and returns them"""
    # Count URL frequencies
    url_counts = df_client['URL'].value_counts()
    suggestions = []
    
    for url, count in url_counts.items():
        # If static asset or file is hit multiple times, recommend caching
        if count >= 3:
            # Estimate savings ($0.05 per egress hit saved)
            savings = count * 0.05
            suggestions.append({
                "url_path": url,
                "hits": int(count),
                "recommended_ttl": 3600,
                "caching_status": "Recommended",
                "estimated_savings": round(savings, 2)
            })
            
    # Write to local edge_rules.json
    try:
        with open("edge_rules.json", "w") as f:
            json.dump(suggestions, f, indent=4)
    except Exception as e:
        print(f"[ERROR] Writing edge_rules.json: {e}")
        
    return suggestions

class LogAnalyzer:  

    def __init__(self, bucket_name, log_key):
        self.bucket_name = bucket_name
        self.log_key = log_key
        self.data = []
        self.s3_client = boto3.client('s3', region_name='us-east-1')

    def parse_logs(self):   
        """Used for reading data from S3 and identify patterns with the help of regex"""
        # IP, Timestamp, URL, Status, and optional Bytes format
        log_pattern = r'(\d+\.\d+\.\d+\.\d+).*?\[(.*?)\].*?"\w+ (.*?)" (\d+)(?: (\d+))?'

        # Retrieve log object from mock S3
        response = self.s3_client.get_object(Bucket=self.bucket_name, Key=self.log_key)
        log_content = response['Body'].read().decode('utf-8')

        # Reset data to prevent duplicates on multiple runs
        self.data = []
        for line in log_content.splitlines():
            # Skip comments and empty lines
            if line.startswith('#') or not line.strip():
                continue
            match = re.search(log_pattern, line)
            if match:
                self.data.append({
                    "IP": match.group(1),
                    "Timestamp": match.group(2),
                    "URL": match.group(3),
                    "Status": int(match.group(4)),
                    "Bytes": int(match.group(5)) if match.group(5) else 1024
                })

        # convert Data to Pandas table
        self.df = pd.DataFrame(self.data)

    def security_audit(self):   
        """Flags IPs with more than 5 failed login attempts (HTTP 401)"""
        # Filter for failed login attempts (status 401)
        failed_logins = self.df[self.df['Status'] == 401]
        
        if failed_logins.empty:
            return pd.Series(dtype=int)
            
        ip_counts = failed_logins['IP'].value_counts()
        suspected = ip_counts[ip_counts > 5]
        return suspected

    def evaluate_self_healing(self):
        """Scans logs for consecutive 500 server crashes and triggers virtual EC2 auto-scaling"""
        global scaled_instances, auto_scaling_triggered
        
        if self.df.empty:
            return "Healthy", 0
            
        consecutive_failures = 0
        max_consecutive = 0
        
        for status in self.df['Status']:
            if status == 500:
                consecutive_failures += 1
                if consecutive_failures > max_consecutive:
                    max_consecutive = consecutive_failures
            else:
                consecutive_failures = 0

        # If server crashed consecutively >= 5 times and scaling hasn't been triggered yet
        if max_consecutive >= 5:
            if not auto_scaling_triggered:
                print(f"[!] Critical crashes detected ({max_consecutive} failures). Triggering Auto-scaling...")
                try:
                    ec2_client = boto3.client('ec2', region_name='us-east-1')
                    response = ec2_client.run_instances(
                        ImageId='ami-0c55b159cbfafe1f0', # Mock AMI
                        MinCount=1,
                        MaxCount=1,
                        InstanceType='t2.micro'
                    )
                    instance_id = response['Instances'][0]['InstanceId']
                    scaled_instances.append({
                        "instance_id": instance_id,
                        "status": "Running",
                        "type": "t2.micro",
                        "time": time.strftime("%H:%M:%S")
                    })
                    auto_scaling_triggered = True
                except Exception as e:
                    print(f"[ERROR] Failed to launch recovery EC2 instance: {e}")
            return "Crashed (Auto-Scaling Active)", max_consecutive
        else:
            # If server recovered (normal status codes appeared at the end of logs)
            if auto_scaling_triggered and max_consecutive == 0:
                print("[+] Server has stabilized. Resetting auto-scaler.")
                auto_scaling_triggered = False
            return "Healthy", max_consecutive

# Lifespan Context Manager to handle S3 Mock setup & teardown
@asynccontextmanager
async def lifespan(app: FastAPI):
    global mock_env
    mock_env = setup_mock_s3()
    yield
    if mock_env:
        print("[*] Stopping Virtual AWS S3 environment...")
        mock_env.stop()

# Initialize FastAPI App
app = FastAPI(
    title="Cloud-Shield AI Engine",
    description="SaaS Observability & Self-Healing log processing API backend",
    lifespan=lifespan
)

# CORS middleware config to allow React Frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "running", "service": "Cloud-Shield AI Observability Engine"}

@app.get("/api/stats")
def get_stats():
    """Fetches stats from S3 logs and returns aggregated details"""
    try:
        analyzer = LogAnalyzer(BUCKET_NAME, LOG_KEY)
        analyzer.parse_logs()
        
        if analyzer.df.empty:
            return {
                "total_requests": 0, 
                "status_codes": {}, 
                "ips": {},
                "edge_rules": []
            }
            
        total_requests = len(analyzer.df)
        status_counts = analyzer.df['Status'].value_counts().to_dict()
        ip_counts = analyzer.df['IP'].value_counts().to_dict()
        
        # Convert integer keys to string for JSON compatibility
        status_counts_str = {str(k): int(v) for k, v in status_counts.items()}
        ip_counts_str = {str(k): int(v) for k, v in ip_counts.items()}
        
        # Generate FinOps caching rules suggestions
        edge_rules = generate_edge_rules(analyzer.df)
        
        return {
            "total_requests": total_requests,
            "status_codes": status_counts_str,
            "ips": ip_counts_str,
            "edge_rules": edge_rules
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/security")
def get_security_audit():
    """Runs security audit and flags brute force attackers"""
    try:
        analyzer = LogAnalyzer(BUCKET_NAME, LOG_KEY)
        analyzer.parse_logs()
        
        suspected = analyzer.security_audit()
        suspected_dict = {str(k): int(v) for k, v in suspected.items()}
        
        return {
            "suspicious_ips": suspected_dict
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/healing")
def get_self_healing_status():
    """Evaluates log health and returns the self-healing auto-scaling status"""
    try:
        analyzer = LogAnalyzer(BUCKET_NAME, LOG_KEY)
        analyzer.parse_logs()
        
        health_status, consecutive_crashes = analyzer.evaluate_self_healing()
        
        return {
            "health_status": health_status,
            "consecutive_crashes": consecutive_crashes,
            "auto_scaling_triggered": auto_scaling_triggered,
            "instances": scaled_instances
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/log")
def add_log(payload: dict):
    """Appends new log line from dummy app to local server.log and re-uploads to mock S3"""
    try:
        log_line = payload.get("log_line")
        if not log_line:
            return {"error": "log_line is required"}
            
        # Append to server.log locally
        with open("server.log", "a") as f:
            f.write(log_line + "\n")
            
        # Upload updated log file to virtual S3
        s3_client = boto3.client('s3', region_name='us-east-1')
        s3_client.upload_file('server.log', BUCKET_NAME, LOG_KEY)
        
        return {"status": "success", "message": "Log synced to virtual S3"}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    # Starts server on port 8000
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
