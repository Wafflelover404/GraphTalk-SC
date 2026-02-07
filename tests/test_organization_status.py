#!/usr/bin/env python3
"""
Test Organization Rejection and Status Change Functionality
Tests the new organization management endpoints:
- Reject organization
- Change organization status (active -> pending, etc.)
"""
import asyncio
import aiohttp
import json
import time
from datetime import datetime

class OrganizationStatusTest:
    def __init__(self, base_url="http://localhost:9001"):
        self.base_url = base_url
        self.admin_token = None
        self.test_org_id = None
        self.test_results = []
        
    def log(self, message, status="INFO"):
        """Log test steps"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {status}: {message}")
        self.test_results.append({"time": timestamp, "status": status, "message": message})
        
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
                        token = auth_data.get("token")
                        self.log(f"✅ User logged in successfully")
                        return token
                    else:
                        error = await resp.text()
                        self.log(f"❌ Login failed: {error}", "ERROR")
                        return None
            except Exception as e:
                self.log(f"❌ Login error: {e}", "ERROR")
                return None
    
    async def create_test_organization(self, org_name, admin_username, admin_password):
        """Create a test organization"""
        self.log(f"Creating test organization: {org_name}")
        
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
                        self.log(f"✅ Organization created: {result.get('message')}")
                        return result
                    else:
                        error = await resp.text()
                        self.log(f"❌ Organization creation failed: {error}", "ERROR")
                        return None
            except Exception as e:
                self.log(f"❌ Organization creation error: {e}", "ERROR")
                return None
    
    async def get_all_organizations(self):
        """Get all organizations"""
        self.log("Fetching all organizations")
        
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
    
    async def approve_organization(self, org_id):
        """Approve an organization"""
        self.log(f"Approving organization: {org_id}")
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.admin_token}"}
            
            try:
                async with session.post(f"{self.base_url}/organizations/approve/{org_id}", headers=headers) as resp:
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
    
    async def reject_organization(self, org_id, reason=""):
        """Reject an organization"""
        self.log(f"Rejecting organization: {org_id}")
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.admin_token}"}
            reject_data = {"reason": reason} if reason else {}
            
            try:
                async with session.post(f"{self.base_url}/organizations/reject/{org_id}", json=reject_data, headers=headers) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        self.log(f"✅ Organization rejected: {result.get('message')}")
                        return True
                    else:
                        error = await resp.text()
                        self.log(f"❌ Rejection failed: {error}", "ERROR")
                        return False
            except Exception as e:
                self.log(f"❌ Rejection error: {e}", "ERROR")
                return False
    
    async def change_organization_status(self, org_id, new_status):
        """Change organization status"""
        self.log(f"Changing organization {org_id} status to: {new_status}")
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.admin_token}"}
            status_data = {"status": new_status}
            
            try:
                async with session.post(f"{self.base_url}/organizations/change-status/{org_id}", json=status_data, headers=headers) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        self.log(f"✅ Status changed: {result.get('message')}")
                        return True
                    else:
                        error = await resp.text()
                        self.log(f"❌ Status change failed: {error}", "ERROR")
                        return False
            except Exception as e:
                self.log(f"❌ Status change error: {e}", "ERROR")
                return False
    
    async def test_login_after_status_change(self, username, password, should_succeed):
        """Test login after status change"""
        self.log(f"Testing login for {username} (should {'succeed' if should_succeed else 'fail'})")
        
        token = await self.login_user(username, password)
        if should_succeed:
            return token is not None
        else:
            return token is None
    
    def get_org_status(self, orgs, org_id):
        """Get organization status from list"""
        for org in orgs:
            if org.get("id") == org_id:
                return org.get("status")
        return None
    
    async def run_comprehensive_test(self):
        """Run comprehensive organization status test"""
        self.log("🚀 Starting Organization Status Management Test")
        self.log("=" * 60)
        
        # Step 1: Login as admin
        self.log("Step 1: Admin Login")
        self.admin_token = await self.login_user("test", "test")
        if not self.admin_token:
            self.log("❌ Failed to login as admin", "ERROR")
            return False
        
        # Step 2: Create test organization
        self.log("\nStep 2: Create Test Organization")
        timestamp = int(time.time())
        org_name = f"Status Test Org {timestamp}"
        admin_username = f"statustest_{timestamp}"
        admin_password = "testpass123"
        
        org_result = await self.create_test_organization(org_name, admin_username, admin_password)
        if not org_result:
            self.log("❌ Failed to create organization", "ERROR")
            return False
        
        # Get organization ID
        admin_orgs = await self.get_all_organizations()
        if not admin_orgs:
            self.log("❌ Failed to fetch organizations", "ERROR")
            return False
        
        test_org = None
        for org in admin_orgs:
            if org_name in org.get("name", ""):
                test_org = org
                break
        
        if not test_org:
            self.log("❌ Could not find created organization", "ERROR")
            return False
        
        self.test_org_id = test_org.get("id")
        initial_status = test_org.get("status")
        self.log(f"✅ Found organization: {self.test_org_id}, Status: {initial_status}")
        
        # Step 3: Test rejection
        self.log("\nStep 3: Test Organization Rejection")
        reject_success = await self.reject_organization(self.test_org_id, "Test rejection for workflow")
        
        if reject_success:
            await asyncio.sleep(1)  # Brief pause
            admin_orgs_after_reject = await self.get_all_organizations()
            rejected_status = self.get_org_status(admin_orgs_after_reject, self.test_org_id)
            self.log(f"📊 Status after rejection: {rejected_status}")
            
            # Test login after rejection (should fail)
            login_after_reject = await self.test_login_after_status_change(admin_username, admin_password, False)
            self.log(f"📝 Login after rejection: {'Blocked correctly' if not login_after_reject else 'Unexpectedly allowed'}")
        
        # Step 4: Test status change from rejected to pending
        self.log("\nStep 4: Test Status Change (Rejected -> Pending)")
        status_change_1 = await self.change_organization_status(self.test_org_id, "pending")
        
        if status_change_1:
            await asyncio.sleep(1)
            admin_orgs_after_change1 = await self.get_all_organizations()
            pending_status = self.get_org_status(admin_orgs_after_change1, self.test_org_id)
            self.log(f"📊 Status after change to pending: {pending_status}")
            
            # Test login after status change to pending (should still fail)
            login_after_pending = await self.test_login_after_status_change(admin_username, admin_password, False)
            self.log(f"📝 Login after pending: {'Blocked correctly' if not login_after_pending else 'Unexpectedly allowed'}")
        
        # Step 5: Approve organization
        self.log("\nStep 5: Test Organization Approval")
        approve_success = await self.approve_organization(self.test_org_id)
        
        if approve_success:
            await asyncio.sleep(1)
            admin_orgs_after_approve = await self.get_all_organizations()
            approved_status = self.get_org_status(admin_orgs_after_approve, self.test_org_id)
            self.log(f"📊 Status after approval: {approved_status}")
            
            # Test login after approval (should succeed)
            login_after_approve = await self.test_login_after_status_change(admin_username, admin_password, True)
            self.log(f"📝 Login after approval: {'Allowed correctly' if login_after_approve else 'Unexpectedly blocked'}")
        
        # Step 6: Test status change from active back to pending
        self.log("\nStep 6: Test Status Change (Active -> Pending)")
        status_change_2 = await self.change_organization_status(self.test_org_id, "pending")
        
        if status_change_2:
            await asyncio.sleep(1)
            admin_orgs_after_change2 = await self.get_all_organizations()
            back_to_pending_status = self.get_org_status(admin_orgs_after_change2, self.test_org_id)
            self.log(f"📊 Status after change back to pending: {back_to_pending_status}")
            
            # Test login after changing back to pending (should fail again)
            login_after_back_to_pending = await self.test_login_after_status_change(admin_username, admin_password, False)
            self.log(f"📝 Login after back to pending: {'Blocked correctly' if not login_after_back_to_pending else 'Unexpectedly allowed'}")
        
        # Step 7: Test invalid status change
        self.log("\nStep 7: Test Invalid Status Change")
        invalid_status_change = await self.change_organization_status(self.test_org_id, "invalid_status")
        self.log(f"📝 Invalid status change: {'Rejected correctly' if not invalid_status_change else 'Unexpectedly allowed'}")
        
        # Summary
        self.log("\n📋 COMPREHENSIVE TEST SUMMARY")
        self.log("=" * 60)
        self.log(f"✅ Organization ID: {self.test_org_id}")
        self.log(f"✅ Organization Name: {org_name}")
        self.log(f"✅ Admin Username: {admin_username}")
        self.log(f"✅ Initial Status: {initial_status}")
        self.log(f"✅ Rejection Success: {reject_success}")
        self.log(f"✅ Status Change (Rejected->Pending): {status_change_1}")
        self.log(f"✅ Approval Success: {approve_success}")
        self.log(f"✅ Status Change (Active->Pending): {status_change_2}")
        self.log(f"✅ Invalid Status Change Rejected: {not invalid_status_change}")
        
        # Save test results
        await self.save_test_results()
        
        return True
    
    async def save_test_results(self):
        """Save test results to file"""
        results_file = f"organization_status_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(results_file, 'w') as f:
            json.dump({
                "test_name": "Organization Status Management Test",
                "timestamp": datetime.now().isoformat(),
                "organization_id": self.test_org_id,
                "results": self.test_results
            }, f, indent=2)
        
        self.log(f"📄 Test results saved to: {results_file}")

async def main():
    """Main test runner"""
    tester = OrganizationStatusTest()
    
    print("🧪 Organization Status Management Test")
    print("=" * 60)
    print("This test will:")
    print("1. Create a test organization")
    print("2. Test organization rejection")
    print("3. Test status change (rejected -> pending)")
    print("4. Test organization approval")
    print("5. Test status change (active -> pending)")
    print("6. Test invalid status change")
    print("7. Verify login behavior at each stage")
    print()
    
    success = await tester.run_comprehensive_test()
    
    if success:
        print("\n🎉 Organization status management test completed successfully!")
    else:
        print("\n❌ Organization status management test failed!")

if __name__ == "__main__":
    asyncio.run(main())
