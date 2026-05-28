import pandas as pd 
import matplotlib.pyplot as plt 
import re   
from collections import Counter
import boto3
from moto import mock_aws

def setup_mock_s3():
    """Starts mock S3, creates the virtual bucket, and uploads the local server.log"""
    print("[*] Initializing Virtual AWS S3 environment...")
    mock = mock_aws()
    mock.start()
    
    s3_client = boto3.client('s3', region_name='us-east-1')
    bucket_name = 'cloud-shield-logs-bucket'
    s3_client.create_bucket(Bucket=bucket_name)
    
    # Upload local log file to our mock bucket
    print(f"[*] Uploading 'server.log' to S3 bucket '{bucket_name}'...")
    s3_client.upload_file('server.log', bucket_name, 'raw_logs/server.log')
    return mock

class LogAnalyzer:  

    def __init__(self, bucket_name, log_key):
        self.bucket_name = bucket_name
        self.log_key = log_key
        self.data = []
        self.s3_client = boto3.client('s3', region_name='us-east-1')

    def parse_logs(self):   
        """Used for reading data from S3 and identify patterns with the help of regex"""
        print("[*] Fetching and parsing logs from Virtual S3...")    

        # this pattern used to detect IP, Date, aur Status format
        log_pattern = r'(\d+\.\d+\.\d+\.\d+).*?\[(.*?)\].*?"\w+.*?" (\d+)'

        # Retrieve log object from mock S3
        response = self.s3_client.get_object(Bucket=self.bucket_name, Key=self.log_key)
        log_content = response['Body'].read().decode('utf-8')

        for line in log_content.splitlines():
            match = re.search(log_pattern, line)
            if match:
                self.data.append({
                    "IP": match.group(1),
                    "Timestamp": match.group(2),
                    "Status": int(match.group(3))
                })

        # convert Data to Pandas table
        self.df = pd.DataFrame(self.data)

    def security_audit(self):   
        """Hacker detect karne ka logic"""
        print("[!] Performing Security Audit...")
        ip_counts = self.df['IP'].value_counts()
        
        # Real Example: If IP detect more than 5 times (Potential Attack)
        suspected = ip_counts[ip_counts > 5]
        return suspected

    def generate_visuals(self): 
        """function to make graph"""
        plt.figure(figsize=(10, 5))

        # Subplot 1: Traffic
        plt.subplot(1, 2, 1)
        self.df['IP'].value_counts().plot(kind='pie', autopct='%1.1f%%')
        plt.title("Traffic Distribution (IP)")

        # Subplot 2: Status Codes
        plt.subplot(1, 2, 2)
        self.df['Status'].value_counts().plot(kind='bar', color='red')
        plt.title("Error vs Success Codes")

        plt.tight_layout()
        plt.savefig('analysis_report.png') # Report saves as image
        plt.close() # Close to release memory/avoid blocking

    def save_report(self):
        """Summary file making"""   
        summary = self.df.describe()
        summary.to_csv("final_report.csv")
        print("[+] Report saved as 'final_report.csv' and 'analysis_report.png'")

# --- Program Start ---
if __name__ == "__main__":
    # Start the local S3 simulator
    mock_env = setup_mock_s3()

    try:
        # Give Bucket name and key path in mock S3
        analyzer = LogAnalyzer('cloud-shield-logs-bucket', 'raw_logs/server.log') 
        analyzer.parse_logs()

        # Logic Run 
        suspicious_ips = analyzer.security_audit()  
        print(f"\nSuspicious IPs Found:\n{suspicious_ips}")

        analyzer.save_report()  
        analyzer.generate_visuals()
    finally:
        # Stop the mock environment
        print("[*] Stopping Virtual AWS S3 environment...")
        mock_env.stop()
