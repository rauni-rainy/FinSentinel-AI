import urllib.request
import time
import sys
import subprocess

def test_health():
    url = "http://localhost:8000/health"
    max_retries = 30
    
    print("Starting docker containers...")
    # Use standard shell on windows
    subprocess.run("docker compose up -d --build", shell=True, check=True)
    
    print(f"Waiting for {url} to be available...")
    for i in range(max_retries):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    data = response.read().decode('utf-8')
                    print(f"Success! Backend is reachable. Response: {data}")
                    
                    # Next, test if frontend is available
                    frontend_url = "http://localhost:3000"
                    print(f"Waiting for {frontend_url} to be available...")
                    for j in range(max_retries):
                        try:
                            f_req = urllib.request.Request(frontend_url)
                            with urllib.request.urlopen(f_req) as f_response:
                                if f_response.status == 200:
                                    print("Success! Frontend is reachable.")
                                    return True
                        except Exception as e:
                            time.sleep(2)
                    print("Frontend not reachable.")
                    return False
        except Exception as e:
            print(f"Retry {i+1}/{max_retries}: {e}")
            time.sleep(2)
            
    print("Timeout waiting for backend.")
    return False

if __name__ == "__main__":
    success = test_health()
    
    print("\nBringing down containers...")
    subprocess.run("docker compose down", shell=True)
    
    if not success:
        sys.exit(1)
    print("Smoke test passed successfully!")
