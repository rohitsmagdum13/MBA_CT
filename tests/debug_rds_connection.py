"""
RDS Connection Debugger - Comprehensive diagnostics for MySQL connectivity issues.

Run this script to diagnose connection problems step by step.
"""

import sys
import socket
import pymysql
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from MBA.core.settings import settings
from MBA.core.logging_config import get_logger, setup_root_logger

setup_root_logger()
logger = get_logger(__name__)


def check_dns_resolution():
    """Step 1: Check if DNS resolves the RDS endpoint."""
    print("\n" + "="*60)
    print("STEP 1: DNS Resolution Check")
    print("="*60)
    
    try:
        host = settings.RDS_HOST
        print(f"Attempting to resolve: {host}")
        
        ip = socket.gethostbyname(host)
        print(f"✓ DNS resolved successfully to: {ip}")
        return True, ip
    except socket.gaierror as e:
        print(f"✗ DNS resolution failed: {e}")
        print("\nTROUBLESHOOTING:")
        print("- Check if the RDS endpoint is correct in your .env file")
        print("- Verify the RDS instance exists in AWS Console")
        return False, None


def check_port_connectivity(host, ip):
    """Step 2: Check if port 3306 is reachable."""
    print("\n" + "="*60)
    print("STEP 2: Port Connectivity Check")
    print("="*60)
    
    port = settings.RDS_PORT
    print(f"Attempting to connect to: {host}:{port} ({ip}:{port})")
    print("Timeout: 5 seconds...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"✓ Port {port} is OPEN and accepting connections")
            return True
        else:
            print(f"✗ Port {port} is CLOSED or filtered (error code: {result})")
            print("\nTROUBLESHOOTING:")
            print("- RDS Security Group must allow inbound TCP on port 3306")
            print("- Add your public IP to the security group inbound rules")
            print("- Check if RDS is 'Publicly Accessible' (must be enabled)")
            return False
            
    except socket.timeout:
        print(f"✗ Connection TIMED OUT after 5 seconds")
        print("\nTROUBLESHOOTING:")
        print("- Security group is likely blocking the connection")
        print("- RDS may not be publicly accessible")
        print("- Your IP may not be in the allowed CIDR range")
        return False
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False


def check_mysql_auth():
    """Step 3: Attempt MySQL authentication."""
    print("\n" + "="*60)
    print("STEP 3: MySQL Authentication Check")
    print("="*60)
    
    print(f"Host:     {settings.RDS_HOST}")
    print(f"Port:     {settings.RDS_PORT}")
    print(f"Database: {settings.RDS_DATABASE}")
    print(f"Username: {settings.RDS_USERNAME}")
    print(f"Password: {'*' * len(settings.RDS_PASSWORD) if settings.RDS_PASSWORD else 'NOT SET'}")
    print("\nAttempting MySQL connection...")
    
    try:
        connection = pymysql.connect(
            host=settings.RDS_HOST,
            port=settings.RDS_PORT,
            user=settings.RDS_USERNAME,
            password=settings.RDS_PASSWORD,
            database=settings.RDS_DATABASE,
            connect_timeout=10
        )
        
        print("✓ Successfully connected to MySQL!")
        
        # Test query
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION(), DATABASE(), USER()")
            result = cursor.fetchone()
            print(f"\nMySQL Version: {result[0]}")
            print(f"Database:      {result[1]}")
            print(f"User:          {result[2]}")
        
        connection.close()
        return True
        
    except pymysql.err.OperationalError as e:
        error_code, error_msg = e.args
        print(f"✗ MySQL connection failed: ({error_code}) {error_msg}")
        
        if error_code == 2003:
            print("\nTROUBLESHOOTING:")
            print("- Can't reach MySQL server (network issue)")
            print("- Verify security group allows port 3306 from your IP")
            print("- Ensure RDS is publicly accessible")
        elif error_code == 1045:
            print("\nTROUBLESHOOTING:")
            print("- Invalid username or password")
            print("- Check credentials in .env file")
            print("- Verify user has access from your IP (MySQL user host)")
        elif error_code == 1049:
            print("\nTROUBLESHOOTING:")
            print("- Database does not exist")
            print("- Create the database or update RDS_DATABASE in .env")
        
        return False
        
    except Exception as e:
        print(f"✗ Unexpected error: {type(e).__name__}: {e}")
        return False


def check_aws_credentials():
    """Step 4: Verify AWS credentials for boto3."""
    print("\n" + "="*60)
    print("STEP 4: AWS Credentials Check")
    print("="*60)
    
    import boto3
    
    try:
        session = boto3.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_default_region
        )
        
        sts = session.client('sts')
        identity = sts.get_caller_identity()
        
        print("✓ AWS credentials are valid")
        print(f"Account: {identity['Account']}")
        print(f"User/Role: {identity['Arn']}")
        return True
        
    except Exception as e:
        print(f"✗ AWS credentials invalid: {e}")
        print("\nTROUBLESHOOTING:")
        print("- Check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env")
        print("- Verify credentials have necessary permissions")
        return False


def print_network_diagnostics():
    """Print additional network diagnostic info."""
    print("\n" + "="*60)
    print("NETWORK DIAGNOSTICS")
    print("="*60)
    
    # Get public IP
    try:
        import requests
        public_ip = requests.get('https://api.ipify.org', timeout=5).text
        print(f"Your Public IP: {public_ip}")
        print(f"\nThis IP must be allowed in RDS Security Group!")
        print(f"Add inbound rule: Type=MySQL/Aurora, Port=3306, Source={public_ip}/32")
    except:
        print("Could not determine public IP")
    
    # DNS servers
    print(f"\nDNS Configuration: Using system default")


def print_aws_cli_commands():
    """Print helpful AWS CLI commands for debugging."""
    print("\n" + "="*60)
    print("AWS CLI DEBUGGING COMMANDS")
    print("="*60)
    
    print("\n# Check RDS instance status:")
    print("aws rds describe-db-instances --db-instance-identifier mba-mysql-db")
    
    print("\n# Check if publicly accessible:")
    print("aws rds describe-db-instances --db-instance-identifier mba-mysql-db --query 'DBInstances[0].PubliclyAccessible'")
    
    print("\n# Enable public access:")
    print("aws rds modify-db-instance --db-instance-identifier mba-mysql-db --publicly-accessible --apply-immediately")
    
    print("\n# Get security group ID:")
    print("aws rds describe-db-instances --db-instance-identifier mba-mysql-db --query 'DBInstances[0].VpcSecurityGroups[0].VpcSecurityGroupId'")
    
    print("\n# Check security group rules (replace sg-xxxxx):")
    print("aws ec2 describe-security-groups --group-ids sg-xxxxx")
    
    print("\n# Add your IP to security group (replace sg-xxxxx and YOUR_IP):")
    print("aws ec2 authorize-security-group-ingress --group-id sg-xxxxx --protocol tcp --port 3306 --cidr YOUR_IP/32")


def main():
    """Run all diagnostic checks."""
    print("\n" + "="*60)
    print("RDS CONNECTION DIAGNOSTIC TOOL")
    print("="*60)
    print("This tool will help diagnose RDS connectivity issues")
    
    # Check environment variables
    print("\n" + "="*60)
    print("ENVIRONMENT CONFIGURATION")
    print("="*60)
    print(f"RDS_HOST:     {settings.RDS_HOST}")
    print(f"RDS_PORT:     {settings.RDS_PORT}")
    print(f"RDS_DATABASE: {settings.RDS_DATABASE}")
    print(f"RDS_USERNAME: {settings.RDS_USERNAME}")
    print(f"RDS_PASSWORD: {'SET' if settings.RDS_PASSWORD else 'NOT SET'}")
    print(f"AWS_REGION:   {settings.aws_default_region}")
    
    # Run diagnostic steps
    dns_ok, ip = check_dns_resolution()
    if not dns_ok:
        print("\n❌ FAILED: Cannot proceed without valid DNS resolution")
        print_aws_cli_commands()
        sys.exit(1)
    
    port_ok = check_port_connectivity(settings.RDS_HOST, ip)
    if not port_ok:
        print("\n❌ FAILED: Port is not accessible")
        print_network_diagnostics()
        print_aws_cli_commands()
        sys.exit(1)
    
    mysql_ok = check_mysql_auth()
    if not mysql_ok:
        print("\n❌ FAILED: Cannot authenticate with MySQL")
        print_aws_cli_commands()
        sys.exit(1)
    
    aws_ok = check_aws_credentials()
    
    # Final summary
    print("\n" + "="*60)
    print("DIAGNOSTIC SUMMARY")
    print("="*60)
    print(f"DNS Resolution:  {'✓ PASS' if dns_ok else '✗ FAIL'}")
    print(f"Port Connectivity: {'✓ PASS' if port_ok else '✗ FAIL'}")
    print(f"MySQL Auth:      {'✓ PASS' if mysql_ok else '✗ FAIL'}")
    print(f"AWS Credentials: {'✓ PASS' if aws_ok else '✗ FAIL'}")
    
    if dns_ok and port_ok and mysql_ok:
        print("\n✅ SUCCESS: All checks passed! RDS connection is working.")
        print("\nYou can now run: uv run mba-api")
    else:
        print("\n❌ FAILED: Some checks did not pass. Review the errors above.")
        print_aws_cli_commands()
        sys.exit(1)


if __name__ == "__main__":
    main()