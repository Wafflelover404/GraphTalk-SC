#!/usr/bin/env python3
"""
Organization Isolation Test Suite
Tests that admins can only see and manage their own organization's users and files.
"""

import requests
import json
import sys
from typing import Dict, Any, Optional

# Configuration
API_BASE_URL = "http://localhost:9001"
TIMEOUT = 10


class OrgIsolationTester:
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.org_a_token = None
        self.org_b_token = None
        self.org_a_id = None
        self.org_b_id = None
        self.passed = 0
        self.failed = 0
        self.test_results = []

    def log(self, message: str, level: str = "INFO"):
        """Log a message with level"""
        prefix = f"[{level}]"
        print(f"{prefix} {message}")

    def assert_equal(self, actual: Any, expected: Any, message: str):
        """Assert two values are equal"""
        if actual == expected:
            self.log(f"✓ {message}", "PASS")
            self.passed += 1
            self.test_results.append({"status": "PASS", "message": message})
        else:
            self.log(f"✗ {message} (expected {expected}, got {actual})", "FAIL")
            self.failed += 1
            self.test_results.append({
                "status": "FAIL",
                "message": message,
                "expected": expected,
                "actual": actual
            })

    def assert_in_range(self, actual: int, min_val: int, max_val: int, message: str):
        """Assert a value is in range"""
        if min_val <= actual <= max_val:
            self.log(f"✓ {message}", "PASS")
            self.passed += 1
            self.test_results.append({"status": "PASS", "message": message})
        else:
            self.log(f"✗ {message} (expected {min_val}-{max_val}, got {actual})", "FAIL")
            self.failed += 1
            self.test_results.append({
                "status": "FAIL",
                "message": message,
                "expected": f"{min_val}-{max_val}",
                "actual": actual
            })

    def assert_status(self, response: requests.Response, expected_code: int, message: str):
        """Assert response status code"""
        self.assert_equal(response.status_code, expected_code, message)

    def assert_true(self, condition: bool, message: str):
        """Assert a condition is true"""
        if condition:
            self.log(f"✓ {message}", "PASS")
            self.passed += 1
            self.test_results.append({"status": "PASS", "message": message})
        else:
            self.log(f"✗ {message}", "FAIL")
            self.failed += 1
            self.test_results.append({
                "status": "FAIL",
                "message": message
            })

    def create_organization(self, name: str, admin_username: str, admin_password: str) -> Optional[Dict]:
        """Create an organization with admin user"""
        self.log(f"Creating organization: {name}", "TEST")
        url = f"{self.base_url}/organizations/create_with_admin"
        payload = {
            "organization_name": name,
            "admin_username": admin_username,
            "admin_password": admin_password
        }
        try:
            response = requests.post(url, json=payload, timeout=TIMEOUT)
            self.assert_status(response, 200, f"Create org {name}: status 200")
            
            data = response.json()
            if data.get("status") == "success" and data.get("token"):
                self.log(f"✓ Organization {name} created successfully", "INFO")
                return {
                    "token": data["token"],
                    "admin_username": admin_username,
                    "status": data.get("status")
                }
            else:
                self.log(f"✗ Failed to create org {name}: {data}", "ERROR")
                return None
        except Exception as e:
            self.log(f"✗ Exception creating org {name}: {e}", "ERROR")
            return None

    def register_user(self, token: Optional[str], username: str, password: str, role: str = "user") -> bool:
        """Register a user as admin"""
        if not token:
            self.log(f"✗ Cannot register user {username}: no valid token", "ERROR")
            return False
        self.log(f"Registering user: {username} with role {role}", "TEST")
        url = f"{self.base_url}/register"
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "username": username,
            "password": password,
            "role": role
        }
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    self.log(f"✓ User {username} registered successfully", "INFO")
                    return True
            self.log(f"✗ Failed to register user {username}: {response.status_code} {response.text[:100]}", "ERROR")
            return False
        except Exception as e:
            self.log(f"✗ Exception registering user {username}: {e}", "ERROR")
            return False

    def list_accounts(self, token: Optional[str]) -> Optional[list]:
        """List accounts as admin"""
        if not token:
            self.log("Cannot list accounts: no valid token", "ERROR")
            return None
        self.log("Listing accounts", "TEST")
        url = f"{self.base_url}/accounts"
        headers = {"Authorization": f"Bearer {token}"}
        try:
            response = requests.get(url, headers=headers, timeout=TIMEOUT)
            if response.status_code == 200:
                accounts = response.json()
                self.log(f"✓ Retrieved {len(accounts)} accounts", "INFO")
                return accounts
            else:
                self.log(f"✗ Failed to list accounts: {response.status_code}", "ERROR")
                return None
        except Exception as e:
            self.log(f"✗ Exception listing accounts: {e}", "ERROR")
            return None

    def delete_user(self, token: Optional[str], username: str) -> int:
        """Delete a user and return status code"""
        if not token:
            self.log(f"Cannot delete user {username}: no valid token", "ERROR")
            return 401
        self.log(f"Deleting user: {username}", "TEST")
        url = f"{self.base_url}/user/delete"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"username": username}
        try:
            response = requests.delete(url, headers=headers, params=params, timeout=TIMEOUT)
            return response.status_code
        except Exception as e:
            self.log(f"✗ Exception deleting user {username}: {e}", "ERROR")
            return -1

    def test_organization_isolation(self):
        """Run the full organization isolation test"""
        self.log("=" * 60, "TEST")
        self.log("ORGANIZATION ISOLATION TEST SUITE", "TEST")
        self.log("=" * 60, "TEST")
        
        # Test 1: Create Organization A
        self.log("\n--- Test 1: Create Organization A ---", "TEST")
        org_a = self.create_organization("Company Alpha", "admin_a", "pass_alpha_123")
        self.assert_true(org_a is not None, "Organization A created")
        if org_a:
            self.org_a_token = org_a["token"]

        # Test 2: Create Organization B
        self.log("\n--- Test 2: Create Organization B ---", "TEST")
        org_b = self.create_organization("Company Beta", "admin_b", "pass_beta_456")
        self.assert_true(org_b is not None, "Organization B created")
        if org_b:
            self.org_b_token = org_b["token"]

        # Test 3: Admin A registers User A1
        self.log("\n--- Test 3: Admin A registers User A1 ---", "TEST")
        success = self.register_user(self.org_a_token, "user_a1", "pass_a1", "user")
        self.assert_true(success, "User A1 registered in Org A")

        # Test 4: Admin A registers User A2
        self.log("\n--- Test 4: Admin A registers User A2 ---", "TEST")
        success = self.register_user(self.org_a_token, "user_a2", "pass_a2", "user")
        self.assert_true(success, "User A2 registered in Org A")

        # Test 5: Admin B registers User B1
        self.log("\n--- Test 5: Admin B registers User B1 ---", "TEST")
        success = self.register_user(self.org_b_token, "user_b1", "pass_b1", "user")
        self.assert_true(success, "User B1 registered in Org B")

        # Test 6: Admin A lists accounts (should see only Org A users)
        self.log("\n--- Test 6: Admin A lists accounts ---", "TEST")
        accounts_a = self.list_accounts(self.org_a_token)
        if accounts_a:
            usernames_a = [acc.get("username") for acc in accounts_a]
            self.log(f"Admin A sees users: {usernames_a}", "INFO")
            
            # Admin A should see: admin_a, user_a1, user_a2 (NOT user_b1)
            self.assert_true("admin_a" in usernames_a, "Admin A sees admin_a")
            self.assert_true("user_a1" in usernames_a, "Admin A sees user_a1")
            self.assert_true("user_a2" in usernames_a, "Admin A sees user_a2")
            self.assert_true("user_b1" not in usernames_a, "Admin A does NOT see user_b1 (isolation working)")

        # Test 7: Admin B lists accounts (should see only Org B users)
        self.log("\n--- Test 7: Admin B lists accounts ---", "TEST")
        accounts_b = self.list_accounts(self.org_b_token)
        if accounts_b:
            usernames_b = [acc.get("username") for acc in accounts_b]
            self.log(f"Admin B sees users: {usernames_b}", "INFO")
            
            # Admin B should see: admin_b, user_b1 (NOT user_a1 or user_a2)
            self.assert_true("admin_b" in usernames_b, "Admin B sees admin_b")
            self.assert_true("user_b1" in usernames_b, "Admin B sees user_b1")
            self.assert_true("user_a1" not in usernames_b, "Admin B does NOT see user_a1 (isolation working)")
            self.assert_true("user_a2" not in usernames_b, "Admin B does NOT see user_a2 (isolation working)")

        # Test 8: Admin B tries to delete user_a1 (should fail with 403)
        self.log("\n--- Test 8: Admin B tries to delete user_a1 (cross-org delete) ---", "TEST")
        status = self.delete_user(self.org_b_token, "user_a1")
        self.assert_equal(status, 403, "Admin B cannot delete user_a1 (403 Forbidden)")

        # Test 9: Admin A deletes user_a1 (should succeed)
        self.log("\n--- Test 9: Admin A deletes user_a1 (same-org delete) ---", "TEST")
        status = self.delete_user(self.org_a_token, "user_a1")
        self.assert_equal(status, 200, "Admin A can delete user_a1 (200 OK)")

        # Test 10: Verify user_a1 is deleted (shouldn't appear in list)
        self.log("\n--- Test 10: Verify user_a1 is deleted ---", "TEST")
        accounts_a = self.list_accounts(self.org_a_token)
        if accounts_a:
            usernames_a = [acc.get("username") for acc in accounts_a]
            self.assert_true("user_a1" not in usernames_a, "user_a1 no longer in Org A")

        # Test 11: Admin B tries to delete user_b1 (should succeed)
        self.log("\n--- Test 11: Admin B deletes user_b1 (same-org delete) ---", "TEST")
        status = self.delete_user(self.org_b_token, "user_b1")
        self.assert_equal(status, 200, "Admin B can delete user_b1 (200 OK)")

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print test summary"""
        self.log("\n" + "=" * 60, "SUMMARY")
        self.log(f"PASSED: {self.passed}", "SUMMARY")
        self.log(f"FAILED: {self.failed}", "SUMMARY")
        total = self.passed + self.failed
        percentage = (self.passed / total * 100) if total > 0 else 0
        self.log(f"Success Rate: {percentage:.1f}% ({self.passed}/{total})", "SUMMARY")
        self.log("=" * 60, "SUMMARY")

        # Exit with appropriate code
        sys.exit(0 if self.failed == 0 else 1)


def main():
    """Main entry point"""
    tester = OrgIsolationTester()
    tester.test_organization_isolation()


if __name__ == "__main__":
    main()
