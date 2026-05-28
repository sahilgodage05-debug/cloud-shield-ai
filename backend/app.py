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
    if df_client.empty:
        return []
        
    # Count URL frequencies
    url_counts = df_client['URL'].value_counts()
    suggestions = []
    
    for url, count in url_counts.items():
        # If static asset or file is hit multiple times, recommend caching
        if count >= 3:
            # Filter for this URL to calculate average bytes
            url_data = df_client[df_client['URL'] == url]
            avg_bytes = url_data['Bytes'].mean() if 'Bytes' in url_data.columns else 1024
            
            # Bandwidth saved in bytes: (hits - 1) * file_size
            bytes_saved = (count - 1) * avg_bytes
            mb_saved = bytes_saved / (1024 * 1024)
            gb_saved = bytes_saved / (1024 * 1024 * 1024)
            
            # AWS Egress savings ($0.08 per GB) + Server compute overhead saved ($0.05 per hit)
            bandwidth_savings = gb_saved * 0.08
            compute_savings = (count - 1) * 0.05
            total_savings = bandwidth_savings + compute_savings
            
            suggestions.append({
                "url_path": url,
                "hits": int(count),
                "recommended_ttl": 3600,
                "caching_status": "Recommended",
                "avg_bytes": int(avg_bytes),
                "mb_saved": round(mb_saved, 2),
                "estimated_savings": round(total_savings, 2)
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
        # IP, Timestamp, URL, Status, Bytes, optional CPU, and optional Latency
        log_pattern = r'(\d+\.\d+\.\d+\.\d+).*?\[(.*?)\].*?"\w+ (.*?)" (\d+)(?: (\d+))?(?:\s+\[CPU:(\d+)%\])?(?:\s+\[LATENCY:(\d+)ms\])?'

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
                    "Bytes": int(match.group(5)) if match.group(5) else 1024,
                    "CPU": int(match.group(6)) if match.group(6) else 35,       # default CPU 35%
                    "Latency": int(match.group(7)) if match.group(7) else 45    # default Latency 45ms
                })

        # convert Data to Pandas table
        self.df = pd.DataFrame(self.data)

    def security_audit(self):   
        """Flags IPs with 5 or more failed login attempts (HTTP 401) within a 5-second window"""
        print("[!] Performing Security Audit for Brute Force (5-second window)...")
        
        if self.df.empty:
            return pd.Series(dtype=int)
            
        # Parse timestamp strings into datetime objects for mathematical comparison
        try:
            self.df['DateTime'] = pd.to_datetime(self.df['Timestamp'], format='%d/%b/%Y:%H:%M:%S')
        except Exception as e:
            print(f"[ERROR] Date parsing failed: {e}")
            return pd.Series(dtype=int)
            
        # Filter for failed login attempts (status 401)
        failed_logins = self.df[self.df['Status'] == 401].sort_values('DateTime')
        
        if failed_logins.empty:
            return pd.Series(dtype=int)
            
        suspicious_ips = {}
        
        # Check time intervals for each IP address group
        for ip, group in failed_logins.groupby('IP'):
            times = group['DateTime'].tolist()
            if len(times) < 5:
                continue
                
            # If the difference between the 5th attempt and 1st attempt is <= 5 seconds, flag it
            for i in range(4, len(times)):
                time_diff = (times[i] - times[i-4]).total_seconds()
                if time_diff <= 5:
                    suspicious_ips[ip] = len(times)
                    break
                    
        return pd.Series(suspicious_ips, dtype=int)


    def evaluate_self_healing(self):
        """Scans logs for consecutive 500 server crashes and triggers virtual EC2 auto-scaling"""
        global auto_scaling_triggered, scaled_instances
        
        # Determine the current consecutive failures from the end of the log stream
        current_consecutive_failures = 0
        if not self.df.empty:
            for status in reversed(self.df['Status'].tolist()):
                if status == 500:
                    current_consecutive_failures += 1
                else:
                    break

        # Extract latest CPU and Latency metrics
        latest_cpu = 35
        latest_latency = 45
        if not self.df.empty:
            if 'CPU' in self.df.columns and not self.df['CPU'].empty:
                latest_cpu = int(self.df['CPU'].iloc[-1])
            if 'Latency' in self.df.columns and not self.df['Latency'].empty:
                latest_latency = int(self.df['Latency'].iloc[-1])

        # Define both servers
        server_1 = {
            "instance_id": "i-01primaryec2",
            "name": "Primary Server (Server 1)",
            "type": "t2.micro",
            "status": "Running",
            "role": "Primary",
            "time": "09:00:00"
        }
        server_2 = {
            "instance_id": "i-02backup-ec2",
            "name": "Backup Server (Server 2)",
            "type": "t2.micro",
            "status": "Stopped",
            "role": "Backup",
            "time": "N/A"
        }

        # Initialize status variables
        system_mode = "Stable"
        crash_probability = 0.0
        health_status = "Healthy"

        # Case 1: Hard crash (reactive recovery)
        if current_consecutive_failures >= 5:
            server_1["status"] = "Crashed"
            server_2["status"] = "Running"
            system_mode = "Reactive Recovery"
            crash_probability = 100.0
            health_status = "Crashed (Auto-Scaling Active)"
            
            if not auto_scaling_triggered:
                print(f"[!] Critical crashes detected ({current_consecutive_failures} failures). Triggering Auto-scaling...")
                try:
                    ec2_client = boto3.client('ec2', region_name='us-east-1')
                    response = ec2_client.run_instances(
                        ImageId='ami-0c55b159cbfafe1f0',
                        MinCount=1,
                        MaxCount=1,
                        InstanceType='t2.micro'
                    )
                    server_2["instance_id"] = response['Instances'][0]['InstanceId']
                except Exception as e:
                    print(f"[ERROR] Failed to launch recovery EC2 instance: {e}")
                auto_scaling_triggered = True
            server_2["time"] = time.strftime("%H:%M:%S")

        # Case 2: Pre-emptive Load Warning (predictive healing)
        elif latest_cpu >= 85 and latest_latency >= 300:
            server_1["status"] = "Warning"
            server_2["status"] = "Running"
            system_mode = "Predictive Warning"
            
            # Estimate crash probability: base 50% + CPU factor + Latency factor
            calculated_prob = 50.0 + (latest_cpu - 80) * 2.5 + (latest_latency - 300) * 0.08
            crash_probability = round(min(98.0, calculated_prob), 1)
            health_status = "Warning: High Crash Risk"
            
            if not auto_scaling_triggered:
                print(f"[AI SHIELD] Pre-emptive anomaly detected (CPU: {latest_cpu}%, Latency: {latest_latency}ms). Launching backup server...")
                try:
                    ec2_client = boto3.client('ec2', region_name='us-east-1')
                    response = ec2_client.run_instances(
                        ImageId='ami-0c55b159cbfafe1f0',
                        MinCount=1,
                        MaxCount=1,
                        InstanceType='t2.micro'
                    )
                    server_2["instance_id"] = response['Instances'][0]['InstanceId']
                except Exception as e:
                    print(f"[ERROR] Failed to launch pre-emptive EC2 instance: {e}")
                auto_scaling_triggered = True
            server_2["time"] = time.strftime("%H:%M:%S")

        # Case 3: Healthy/Stable state
        else:
            server_1["status"] = "Running"
            server_2["status"] = "Stopped"
            server_2["time"] = "N/A"
            health_status = "Healthy"
            system_mode = "Stable"
            crash_probability = round(min(45.0, (latest_cpu * 0.3) + (latest_latency * 0.1)), 1)
            auto_scaling_triggered = False

        scaled_instances = [server_1, server_2]
        return health_status, current_consecutive_failures, system_mode, crash_probability, latest_cpu, latest_latency

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
                "edge_rules": [],
                "total_bandwidth_saved_mb": 0.0,
                "bandwidth_savings_usd": 0.0,
                "compute_savings_usd": 8.64,
                "total_savings_usd": 8.64
            }
            
        total_requests = len(analyzer.df)
        status_counts = analyzer.df['Status'].value_counts().to_dict()
        ip_counts = analyzer.df['IP'].value_counts().to_dict()
        
        # Convert integer keys to string for JSON compatibility
        status_counts_str = {str(k): int(v) for k, v in status_counts.items()}
        ip_counts_str = {str(k): int(v) for k, v in ip_counts.items()}
        
        # Generate FinOps caching rules suggestions
        edge_rules = generate_edge_rules(analyzer.df)
        
        # Sum up savings from edge rules
        total_bandwidth_saved_mb = sum(r.get('mb_saved', 0.0) for r in edge_rules)
        bandwidth_savings_usd = sum(r.get('estimated_savings', 0.0) for r in edge_rules)
        compute_savings_usd = 8.64  # Cost saved per month by keeping Server 2 Stopped when healthy
        total_savings_usd = bandwidth_savings_usd + compute_savings_usd
        
        return {
            "total_requests": total_requests,
            "status_codes": status_counts_str,
            "ips": ip_counts_str,
            "edge_rules": edge_rules,
            "total_bandwidth_saved_mb": round(total_bandwidth_saved_mb, 2),
            "bandwidth_savings_usd": round(bandwidth_savings_usd, 2),
            "compute_savings_usd": compute_savings_usd,
            "total_savings_usd": round(total_savings_usd, 2)
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
        
        health_status, consecutive_crashes, system_mode, crash_probability, cpu_utilization, latency_ms = analyzer.evaluate_self_healing()
        
        return {
            "health_status": health_status,
            "consecutive_crashes": consecutive_crashes,
            "auto_scaling_triggered": auto_scaling_triggered,
            "instances": scaled_instances,
            "system_mode": system_mode,
            "crash_probability": crash_probability,
            "cpu_utilization": cpu_utilization,
            "latency_ms": latency_ms
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/log")
def add_log(payload: dict):
    """Appends new log line from dummy app to local server.log and re-uploads to mock S3"""
    try:
        log_line = payload.get("log_line")
        ip = payload.get("ip")
        if not log_line or not ip:
            return {"error": "log_line and ip are required"}
            
        # Check if IP is already blocked before parsing new log
        analyzer = LogAnalyzer(BUCKET_NAME, LOG_KEY)
        analyzer.parse_logs()
        suspicious = analyzer.security_audit()
        
        if ip in suspicious.index:
            return {"status": "blocked", "message": "Access Denied: Your IP is blacklisted!"}
            
        # Append to server.log locally
        with open("server.log", "a") as f:
            f.write(log_line + "\n")
            
        # Upload updated log file to virtual S3
        s3_client = boto3.client('s3', region_name='us-east-1')
        s3_client.upload_file('server.log', BUCKET_NAME, LOG_KEY)
        
        # Re-evaluate to check if this log triggered the block threshold
        analyzer.parse_logs()
        new_suspicious = analyzer.security_audit()
        if ip in new_suspicious.index:
            return {"status": "blocked", "message": "Access Denied: Your IP is now blacklisted!"}
            
        return {"status": "success", "message": "Log synced to virtual S3"}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    # Starts server on port 8000
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
