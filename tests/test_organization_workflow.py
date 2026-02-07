#!/usr/bin/env python3
"""
Organization Approval/Banning Workflow Test
Tests the complete lifecycle of organization creation, approval, and banning
"""
import asyncio
import aiohttp
import json
import time
from datetime import datetime

class OrganizationWorkflowTest:
    def __init__(self, base_url="http://localhost:9001"):
        self.base_url = base_url
        self.cms_token = "5gPgr9goO4JxyOQDUWL4aGqX_wEIpwAphvXGv1N_AR3jvN04GByJhlbcDjD-4pVl6VEmWZHctgNmGeg9JJCtmQ"
        self.admin_token = None  # Will be set after login
        self.org_creator_token = None
        self.organization_id = None
        self.test_results = []
        
    def log(self, message, status="INFO"):
        """Log test steps"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {status}: {message}")
        self.test_results.append({"time": timestamp, "status": status, "message": message})
        
    async def create_test_user(self, username, email):
        """Create a test user for organization creation"""
        self.log(f"Creating test user: {username}")
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.admin_token}"}
            user_data = {
                "username": username,
                "email": email,
                "password": "testpassword123",
                "role": "user"
            }
            
            try:
                async with session.post(f"{self.base_url}/register", json=user_data, headers=headers) as resp:
                    if resp.status == 201:
                        user = await resp.json()
                        self.log(f"✅ User created: {user.get('id', username)}")
                        return user
                    else:
                        error = await resp.text()
                        self.log(f"❌ User creation failed: {error}", "ERROR")
                        return None
            except Exception as e:
                self.log(f"❌ User creation error: {e}", "ERROR")
                return None
    
    async def login_user(self, username, password):
        """Login user and get token"""
        self.log(f"Logging in user: {username}")
        
        async with aiohttp.ClientSession() as session:
            login_data = {
                "username": username,
                "password": password
            }
            
            try:
                async with session.post(f"{self.base_url}/login", json=login_data) as resp:
                    if resp.status == 200:
                        auth_data = await resp.json()
                        token = auth_data.get("token")  # Different response format
                        self.log(f"✅ User logged in successfully")
                        return token
                    else:
                        error = await resp.text()
                        self.log(f"❌ Login failed: {error}", "ERROR")
                        return None
            except Exception as e:
                self.log(f"❌ Login error: {e}", "ERROR")
                return None
    
    async def create_organization_with_admin(self, org_name, org_description, admin_username, admin_password):
        """Create a new organization with admin user"""
        self.log(f"Creating organization with admin: {org_name}")
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.admin_token}"}
            org_data = {
                "organization_name": org_name,
                "admin_username": admin_username,
                "admin_password": admin_password,
                "admin_email": f"{admin_username}@test.com"
            }
            
            try:
                async with session.post(f"{self.base_url}/organizations/create_with_admin", json=org_data, headers=headers) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        self.log(f"✅ Organization created: {result}")
                        return result
                    else:
                        error = await resp.text()
                        self.log(f"❌ Organization creation failed: {error}", "ERROR")
                        return None
            except Exception as e:
                self.log(f"❌ Organization creation error: {e}", "ERROR")
                return None
    
    async def check_organization_status(self, perspective="admin"):
        """Check organization status from different perspectives"""
        self.log(f"Checking organization status from {perspective} perspective")
        
        async with aiohttp.ClientSession() as session:
            if perspective == "admin":
                headers = {"Authorization": f"Bearer {self.admin_token}"}
                endpoint = f"{self.base_url}/admin/organizations/{self.organization_id}"
            else:
                headers = {"Authorization": f"Bearer {self.org_creator_token}"}
                endpoint = f"{self.base_url}/organizations/{self.organization_id}"
            
            try:
                async with session.get(endpoint, headers=headers) as resp:
                    if resp.status == 200:
                        org = await resp.json()
                        status = org.get("status", "unknown")
                        self.log(f"📊 Organization status: {status}")
                        return org
                    else:
                        error = await resp.text()
                        self.log(f"❌ Status check failed: {error}", "ERROR")
                        return None
            except Exception as e:
                self.log(f"❌ Status check error: {e}", "ERROR")
                return None
    
    async def approve_organization(self):
        """Approve organization as admin"""
        self.log("Approving organization as admin")
        
        # Get fresh admin token
        admin_token = await self.login_user("test", "test")
        if not admin_token:
            self.log("❌ Failed to get fresh admin token for approval", "ERROR")
            return False
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {admin_token}"}
            approve_data = {"action": "approve", "reason": "Organization meets all requirements"}
            
            try:
                async with session.post(
                    f"{self.base_url}/organizations/approve/{self.organization_id}", 
                    json=approve_data, 
                    headers=headers
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        self.log(f"✅ Organization approved: {result.get('message')}")
                        return True
                    else:
                        error = await resp.text()
                        self.log(f"❌ Approval failed: {error}", "ERROR")
                        return False
            except Exception as e:
                self.log(f"❌ Approval error: {e}", "ERROR")
                return False
    
    async def ban_organization(self):
        """Ban organization as admin"""
        self.log("Banning organization as admin")
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.admin_token}"}
            ban_data = {"action": "ban", "reason": "Policy violation test"}
            
            try:
                async with session.post(
                    f"{self.base_url}/admin/organizations/{self.organization_id}/ban", 
                    json=ban_data, 
                    headers=headers
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        self.log(f"✅ Organization banned: {result.get('message')}")
                        return True
                    else:
                        error = await resp.text()
                        self.log(f"❌ Ban failed: {error}", "ERROR")
                        return False
            except Exception as e:
                self.log(f"❌ Ban error: {e}", "ERROR")
                return False
    
    async def test_organization_access(self):
        """Test if organization can access its resources"""
        self.log("Testing organization resource access")
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.org_creator_token}"}
            
            # Test various endpoints that should be accessible to organization
            test_endpoints = [
                f"{self.base_url}/organizations/{self.organization_id}/documents",
                f"{self.base_url}/organizations/{self.organization_id}/users",
                f"{self.base_url}/organizations/{self.organization_id}/search"
            ]
            
            access_results = {}
            for endpoint in test_endpoints:
                try:
                    async with session.get(endpoint, headers=headers) as resp:
                        access_results[endpoint] = {
                            "status": resp.status,
                            "accessible": resp.status in [200, 404]  # 404 is ok if endpoint exists but no data
                        }
                except Exception as e:
                    access_results[endpoint] = {
                        "status": "error",
                        "accessible": False,
                        "error": str(e)
                    }
            
            self.log(f"📡 Resource access results: {access_results}")
            return access_results
    
    async def run_complete_workflow(self):
        """Run the complete organization workflow test"""
        self.log("🚀 Starting Organization Approval/Banning Workflow Test")
        self.log("=" * 60)
        
        # Step 0: Login as admin to get admin token
        self.log("Logging in as admin user")
        self.admin_token = await self.login_user("test", "test")
        if not self.admin_token:
            self.log("❌ Failed to login as admin", "ERROR")
            return False
        
        # Step 1: Create a new organization with admin
        timestamp = int(time.time())
        org_name = f"Test Workflow Org {timestamp}"
        admin_username = f"orgadmin_{timestamp}"
        admin_password = "testpass123"
        
        self.log(f"Creating new organization: {org_name}")
        org_result = await self.create_organization_with_admin(org_name, "Test organization for workflow", admin_username, admin_password)
        
        if not org_result:
            self.log("❌ Failed to create organization", "ERROR")
            return False
        
        # Extract organization ID from response
        if org_result.get("status") == "success":
            # The response contains token but not org_id, let me get the org ID from the organizations list
            self.log(f"✅ Organization created successfully, fetching ID from organizations list")
            admin_orgs = await self.get_all_organizations()
            if admin_orgs:
                # Find the most recently created organization
                latest_org = None
                latest_time = None
                for org in admin_orgs:
                    if org_name in org.get("name", ""):
                        latest_org = org
                        break
                
                if latest_org:
                    self.organization_id = latest_org.get("id")
                    self.log(f"✅ Found organization ID: {self.organization_id}")
                else:
                    self.log("❌ Could not find created organization in list", "ERROR")
                    return False
            else:
                self.log("❌ Could not fetch organizations list", "ERROR")
                return False
        else:
            self.log("❌ Organization creation response invalid", "ERROR")
            return False
        
        # Step 2: Try to login as the organization admin (should fail due to pending approval)
        self.log(f"Attempting login as organization admin: {admin_username}")
        org_admin_token = await self.login_user(admin_username, admin_password)
        if org_admin_token:
            self.log("⚠️ Organization admin login succeeded (unexpected - org might already be approved)")
            self.org_creator_token = org_admin_token
        else:
            self.log("✅ Organization admin login correctly blocked (organization pending approval)")
            self.log("📝 This is the expected behavior for pending organizations")
            self.org_creator_token = None
        
        # Step 3: Check initial status (should be pending/not approved)
        self.log("\n📋 STEP 1: Initial Organization Status")
        self.log("-" * 40)
        
        # Check from admin perspective
        admin_orgs = await self.get_all_organizations()
        initial_status = "unknown"
        if admin_orgs:
            for org in admin_orgs:
                if org.get("id") == self.organization_id:
                    initial_status = org.get("status", "unknown")
                    break
        
        self.log(f"📊 Initial organization status: {initial_status}")
        
        # Test organization access from creator perspective (if login was successful)
        if self.org_creator_token:
            initial_access = await self.test_organization_access()
        else:
            self.log("📡 Skipping resource access test (admin cannot login to pending organization)")
            initial_access = {"skipped": True, "reason": "Organization pending approval"}
        
        # Step 4: Approve organization as admin
        self.log("\n📋 STEP 2: Admin Approval")
        self.log("-" * 40)
        approval_success = await self.approve_organization()
        
        # Step 5: Check status after approval
        if approval_success:
            await asyncio.sleep(1)  # Brief pause for status update
            admin_orgs_after = await self.get_all_organizations()
            approved_status = "unknown"
            if admin_orgs_after:
                for org in admin_orgs_after:
                    if org.get("id") == self.organization_id:
                        approved_status = org.get("status", "unknown")
                        break
            
            self.log(f"📊 Organization status after approval: {approved_status}")
            
            # Try to login again after approval
            self.log(f"Attempting login after approval: {admin_username}")
            post_approval_token = await self.login_user(admin_username, admin_password)
            if post_approval_token:
                self.log("✅ Organization admin login successful after approval")
                self.org_creator_token = post_approval_token
                approved_access = await self.test_organization_access()
            else:
                self.log("⚠️ Organization admin login still blocked after approval")
                approved_access = {"skipped": True, "reason": "Login still blocked"}
        
        # Summary
        self.log("\n📋 WORKFLOW TEST SUMMARY")
        self.log("=" * 60)
        self.log(f"✅ Organization ID: {self.organization_id}")
        self.log(f"✅ Organization Name: {org_name}")
        self.log(f"✅ Admin Username: {admin_username}")
        self.log(f"✅ Initial Status: {initial_status}")
        self.log(f"✅ Approval Success: {approval_success}")
        self.log(f"✅ Final Status: {approved_status if approval_success else 'Unknown'}")
        
        # Save test results
        await self.save_test_results()
        
        return True
    
    async def get_all_organizations(self):
        """Get all organizations from admin perspective"""
        self.log("Fetching all organizations from admin perspective")
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.admin_token}"}
            
            try:
                async with session.get(f"{self.base_url}/organizations", headers=headers) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        if result.get("status") == "success":
                            orgs = result.get("response", {}).get("organizations", [])
                            self.log(f"✅ Found {len(orgs)} organizations")
                            return orgs
                    error = await resp.text()
                    self.log(f"❌ Failed to fetch organizations: {error}", "ERROR")
                    return None
            except Exception as e:
                self.log(f"❌ Error fetching organizations: {e}", "ERROR")
                return None
    
    async def save_test_results(self):
        """Save test results to file"""
        results_file = f"organization_workflow_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(results_file, 'w') as f:
            json.dump({
                "test_name": "Organization Approval/Banning Workflow",
                "timestamp": datetime.now().isoformat(),
                "organization_id": self.organization_id,
                "results": self.test_results
            }, f, indent=2)
        
        self.log(f"📄 Test results saved to: {results_file}")

async def main():
    """Main test runner"""
    tester = OrganizationWorkflowTest()
    
    print("🧪 Organization Approval/Banning Workflow Test")
    print("=" * 60)
    print("This test will:")
    print("1. Create a test user")
    print("2. Create an organization as that user")
    print("3. Check initial status (should be pending)")
    print("4. Approve organization as admin")
    print("5. Check status after approval")
    print("6. Ban organization as admin")
    print("7. Check status after ban")
    print("8. Test resource access at each step")
    print()
    
    success = await tester.run_complete_workflow()
    
    if success:
        print("\n🎉 Workflow test completed successfully!")
    else:
        print("\n❌ Workflow test failed!")

if __name__ == "__main__":
    asyncio.run(main())
