import pandas as pd 

import matplotlib.pyplot as plt 

import re   

from collections import Counter

class LogAnalyzer:  

    def __init__(self, file_path):
        self.file_path = file_path
        self.data = []
    '''saves file path which is given by user'''

    def parse_logs(self):   
        """Used for reading data and identify petterns with the help of regex"""
        print("[*] Reading Log File...")    

        # this pattern used to detect IP, Date, aur Status format
        log_pattern = r'(\d+\.\d+\.\d+\.\d+).*?\[(.*?)\].*?"\w+.*?" (\d+)'


        with open(self.file_path, 'r') as file: 

            for line in file:
                match = re.search(log_pattern, line)
                if match:
                    self.data.append({
                        "IP": match.group(1),
                        "Timestamp": match.group(2),
                        "Status": int(match.group(3))
                    }   
                    )


        #convert Data to Pandas table
        self.df = pd.DataFrame(self.data)

    def security_audit(self):   

        """Hacker detect karne ka logic"""
        print("[!] Performing Security Audit...")
        ip_counts = self.df['IP'].value_counts()
        
        # Real Example: If IP detect more than 5 times (Potential Attack)
        suspected = ip_counts[ip_counts > 5]
        return suspected


    def generate_visuals(self): 

        """ function to make graph"""
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
        plt.show()


    def save_report(self):
        """Summary file making"""   

        summary = self.df.describe()
        summary.to_csv("final_report.csv")
        print("[+] Report saved as 'final_report.csv' and 'analysis_report.png'")


# --- Program Start ---
if __name__ == "__main__":
    analyzer = LogAnalyzer('server.log') #  giving File path    

    analyzer.parse_logs()


    # Logic Run 
    suspicious_ips = analyzer.security_audit()  

    print(f"\nSuspicious IPs Found:\n{suspicious_ips}")


    analyzer.save_report()  

    analyzer.generate_visuals()
