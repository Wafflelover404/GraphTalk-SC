#!/usr/bin/env python3
"""
Simple Synchronous Database Initialization for WikiAI Project
Avoids async complexity by using subprocess calls for async functions.
"""

import os
import sys
import logging
import sqlite3
import subprocess
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleDatabaseInitializer:
    """Simple database initialization that avoids async issues"""
    
    def __init__(self):
        self.base_dir = os.path.dirname(__file__)
        
    def log_init(self, db_name: str, status: str = "success", details: str = ""):
        """Log database initialization status"""
        if status == "success":
            logger.info(f"✅ {db_name} initialized {details}")
        else:
            logger.error(f"❌ {db_name} failed: {details}")
    
    def run_async_init(self, module_name: str, init_function: str, db_name: str) -> bool:
        """Run async initialization using subprocess"""
        try:
            script = f"""
import asyncio
import sys
sys.path.append('.')
from {module_name} import {init_function}

async def main():
    try:
        await {init_function}()
        print("SUCCESS")
    except Exception as e:
        print(f"ERROR: {{e}}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
"""
            
            # Write temporary script
            temp_script = os.path.join(self.base_dir, f"temp_{module_name}_init.py")
            with open(temp_script, 'w') as f:
                f.write(script)
            
            # Run the script
            result = subprocess.run(
                [sys.executable, temp_script],
                capture_output=True,
                text=True,
                cwd=self.base_dir
            )
            
            # Clean up
            os.remove(temp_script)
            
            if result.returncode == 0 and "SUCCESS" in result.stdout:
                self.log_init(db_name, "success", "and empty")
                return True
            else:
                error_msg = result.stderr or result.stdout or "Unknown error"
                self.log_init(db_name, "error", error_msg)
                return False
                
        except Exception as e:
            self.log_init(db_name, "error", str(e))
            return False
    
    def clean_database_files(self) -> bool:
        """Remove all existing database files"""
        try:
            db_files = [
                "users.db", "metrics.db", "reports.db", "analytics.db", "rag_app.db",
                "api_keys.db"
            ]
            
            for db_file in db_files:
                db_path = os.path.join(self.base_dir, db_file)
                if os.path.exists(db_path):
                    os.remove(db_path)
                    logger.info(f"🗑️  Removed existing {db_file}")
            
            # Clean data directory
            data_dir = os.path.join(self.base_dir, "data")
            if os.path.exists(data_dir):
                for db_file in os.listdir(data_dir):
                    if db_file.endswith('.db'):
                        db_path = os.path.join(data_dir, db_file)
                        os.remove(db_path)
                        logger.info(f"🗑️  Removed existing data/{db_file}")
            
            # Clean integration toolkit
            toolkit_dir = os.path.join(self.base_dir, "integration_toolkit")
            if os.path.exists(toolkit_dir):
                for root, dirs, files in os.walk(toolkit_dir):
                    for file in files:
                        if file.endswith('.db'):
                            db_path = os.path.join(root, file)
                            os.remove(db_path)
                            rel_path = os.path.relpath(db_path, self.base_dir)
                            logger.info(f"🗑️  Removed existing {rel_path}")
            
            return True
        except Exception as e:
            logger.error(f"❌ Failed to clean database files: {e}")
            return False
    
    def clean_directories(self) -> bool:
        """Remove and recreate required directories"""
        try:
            directories = ["data", "uploads", "chroma_db"]
            
            for directory in directories:
                dir_path = os.path.join(self.base_dir, directory)
                if os.path.exists(dir_path):
                    import shutil
                    shutil.rmtree(dir_path)
                    logger.info(f"🗑️  Removed existing {directory}")
                os.makedirs(dir_path, exist_ok=True)
                logger.info(f"📁 Directory ensured: {directory}")
            
            return True
        except Exception as e:
            logger.error(f"❌ Failed to clean directories: {e}")
            return False
    
    def init_sync_databases(self) -> bool:
        """Initialize synchronous databases"""
        try:
            # Metrics database (synchronous)
            import metricsdb
            metricsdb.init_metrics_db()
            self.log_init("Metrics database (metrics.db)", "success", "and empty")
            
            # Reports database (synchronous)
            import reports_db
            reports_db.init_reports_db()
            self.log_init("Reports database (reports.db)", "success", "and empty")
            
            return True
        except Exception as e:
            self.log_init("Sync databases", "error", str(e))
            return False
    
    def init_analytics_database(self) -> bool:
        """Initialize analytics database without auto-population"""
        try:
            import analytics_core
            
            # Remove existing analytics.db
            analytics_db_path = os.path.join(self.base_dir, "analytics.db")
            if os.path.exists(analytics_db_path):
                os.remove(analytics_db_path)
                logger.info("🗑️  Removed existing analytics.db")
            
            # Create analytics instance
            analytics = analytics_core.AnalyticsCore()
            self.log_init("Analytics database (analytics.db)", "success", "and empty")
            return True
        except Exception as e:
            self.log_init("Analytics database", "error", str(e))
            return False
    
    def init_rag_databases(self) -> bool:
        """Initialize RAG databases"""
        try:
            # Remove existing rag_app.db
            rag_db_path = os.path.join(self.base_dir, "rag_app.db")
            if os.path.exists(rag_db_path):
                os.remove(rag_db_path)
                logger.info("🗑️  Removed existing rag_app.db")
            
            # Add rag_api to path and initialize
            rag_api_path = os.path.join(self.base_dir, 'rag_api')
            if os.path.exists(rag_api_path):
                sys.path.append(rag_api_path)
                from db_utils import create_application_logs, create_document_store
                create_application_logs()
                create_document_store()  # This now includes file_size column
                self.log_init("RAG databases", "success", "and empty")
                return True
            else:
                logger.warning("⚠️  RAG API module not found, skipping RAG databases")
                return True
        except Exception as e:
            self.log_init("RAG databases", "error", str(e))
            return False
    
    def verify_databases(self) -> bool:
        """Verify all databases are properly initialized"""
        try:
            logger.info("📋 Database verification results:")
            
            # Verify user database
            if os.path.exists("users.db"):
                conn = sqlite3.connect("users.db")
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM users")
                user_count = cursor.fetchone()[0]
                logger.info(f"  📄 users.db: {user_count} users")
                conn.close()
            
            # Verify metrics database
            if os.path.exists("metrics.db"):
                conn = sqlite3.connect("metrics.db")
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                logger.info(f"  📄 metrics.db: {len(tables)} tables ({', '.join(tables)})")
                conn.close()
            
            # Verify uploads database
            if os.path.exists("uploads.db"):
                conn = sqlite3.connect("uploads.db")
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM uploads")
                upload_count = cursor.fetchone()[0]
                logger.info(f"  📄 uploads.db: {upload_count} uploads")
                conn.close()
            
            # Verify analytics database
            if os.path.exists("analytics.db"):
                import analytics_core
                analytics = analytics_core.AnalyticsCore()
                daily_data = analytics.get_daily_query_volume(days=7)
                logger.info(f"  📄 analytics.db: {len(daily_data)} daily records")
            
            return True
        except Exception as e:
            logger.error(f"❌ Database verification failed: {e}")
            return False
    
    def get_database_summary(self) -> dict:
        """Get summary of all database files"""
        summary = {}
        
        for root, dirs, files in os.walk(self.base_dir):
            for file in files:
                if file.endswith('.db'):
                    file_path = os.path.join(root, file)
                    size = os.path.getsize(file_path)
                    rel_path = os.path.relpath(file_path, self.base_dir)
                    summary[rel_path] = size
        
        return summary
    
    def initialize_all(self, clean: bool = True) -> bool:
        """Initialize all databases"""
        logger.info("🚀 Starting simple database initialization...")
        
        try:
            # Step 1: Clean existing files and directories
            if clean:
                logger.info("🧹 Cleaning existing databases and directories...")
                if not self.clean_database_files():
                    return False
                if not self.clean_directories():
                    return False
            
            # Step 2: Initialize synchronous databases
            logger.info("🔧 Initializing synchronous databases...")
            if not self.init_sync_databases():
                return False
            
            # Step 3: Initialize async databases using subprocess
            logger.info("🔧 Initializing async databases...")
            async_inits = [
                ("userdb", "init_db", "User database (users.db)"),
                ("orgdb", "init_org_db", "Organizations database (organizations.db)"),
                ("plugin_manager", "init_plugins_db", "Plugin database (data/plugins.db)"),
                ("api_keys", "init_api_keys_db", "API Keys database (api_keys.db)"),
                ("opencart_catalog", "init_catalog_db", "OpenCart database (data/catalogs.db)"),
                ("quizdb", "init_quiz_db", "Quiz database (quiz.db)"),
                ("uploadsdb", "init_uploads_db", "Uploads database (uploads.db)"),
            ]
            
            for module_name, init_function, db_name in async_inits:
                logger.info(f"🔧 Initializing {db_name}...")
                if not self.run_async_init(module_name, init_function, db_name):
                    return False
            
            # Step 4: Initialize analytics and RAG
            logger.info("🔧 Initializing analytics and RAG databases...")
            if not self.init_analytics_database():
                return False
            if not self.init_rag_databases():
                return False
            
            # Step 5: Verify and summarize
            logger.info("🔍 Verifying database initialization...")
            if not self.verify_databases():
                return False
            
            logger.info("📋 Database initialization summary:")
            summary = self.get_database_summary()
            for db_path, size in sorted(summary.items()):
                logger.info(f"  📄 {db_path} ({size} bytes)")
            
            logger.info("🎉 All databases initialized successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
            return False


def main():
    """Main initialization function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Simple Database Initialization for WikiAI")
    parser.add_argument(
        "--no-clean", 
        action="store_true", 
        help="Don't clean existing databases before initialization"
    )
    parser.add_argument(
        "--verify-only", 
        action="store_true", 
        help="Only verify existing databases, don't initialize"
    )
    
    args = parser.parse_args()
    
    initializer = SimpleDatabaseInitializer()
    
    if args.verify_only:
        logger.info("🔍 Verifying existing databases only...")
        initializer.verify_databases()
        summary = initializer.get_database_summary()
        logger.info("📋 Current database files:")
        for db_path, size in sorted(summary.items()):
            logger.info(f"  📄 {db_path} ({size} bytes)")
    else:
        clean = not args.no_clean
        success = initializer.initialize_all(clean=clean)
        if not success:
            sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("🛑 Database initialization interrupted")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
