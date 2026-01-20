#!/usr/bin/env python3
"""
Unified Database Initialization for WikiAI Project
This script handles all database initialization in a single, robust manner.
"""

import asyncio
import os
import sys
import logging
import sqlite3
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Change to graphtalk directory for proper imports
os.chdir(os.path.dirname(__file__))

class DatabaseInitializer:
    """Unified database initialization class"""
    
    def __init__(self):
        self.base_dir = os.path.dirname(__file__)
        self.databases = {}
        
    def log_init(self, db_name: str, status: str = "success", details: str = ""):
        """Log database initialization status"""
        if status == "success":
            logger.info(f"✅ {db_name} initialized {details}")
        else:
            logger.error(f"❌ {db_name} failed: {details}")
    
    def ensure_directory(self, path: str) -> bool:
        """Ensure directory exists"""
        try:
            full_path = os.path.join(self.base_dir, path)
            os.makedirs(full_path, exist_ok=True)
            logger.info(f"📁 Directory ensured: {path}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to create directory {path}: {e}")
            return False
    
    def init_user_database(self) -> bool:
        """Initialize user database with proper schema"""
        try:
            import userdb
            # Use asyncio.run() which handles event loop creation
            asyncio.run(userdb.init_db())
            self.log_init("User database (users.db)", "success", "and empty")
            return True
        except Exception as e:
            self.log_init("User database", "error", str(e))
            return False
    
    def init_metrics_database(self) -> bool:
        """Initialize metrics database with all required tables"""
        try:
            import metricsdb
            metricsdb.init_metrics_db()
            self.log_init("Metrics database (metrics.db)", "success", "and empty")
            return True
        except Exception as e:
            self.log_init("Metrics database", "error", str(e))
            return False
    
    def init_reports_database(self) -> bool:
        """Initialize reports database"""
        try:
            import reports_db
            reports_db.init_reports_db()
            self.log_init("Reports database (reports.db)", "success", "and empty")
            return True
        except Exception as e:
            self.log_init("Reports database", "error", str(e))
            return False
    
    def init_plugins_database(self) -> bool:
        """Initialize plugins database"""
        try:
            import plugin_manager
            asyncio.run(plugin_manager.init_plugins_db())
            self.log_init("Plugin database (data/plugins.db)", "success", "and empty")
            return True
        except Exception as e:
            self.log_init("Plugin database", "error", str(e))
            return False
    
    def init_api_keys_database(self) -> bool:
        """Initialize API keys database"""
        try:
            import api_keys
            asyncio.run(api_keys.init_api_keys_db())
            self.log_init("API Keys database (api_keys.db)", "success", "and empty")
            return True
        except Exception as e:
            self.log_init("API Keys database", "error", str(e))
            return False
    
    def init_opencart_database(self) -> bool:
        """Initialize OpenCart catalog database"""
        try:
            import opencart_catalog
            asyncio.run(opencart_catalog.init_catalog_db())
            self.log_init("OpenCart database (data/catalogs.db)", "success", "and empty")
            return True
        except Exception as e:
            self.log_init("OpenCart database", "error", str(e))
            return False
    
    def init_analytics_database(self) -> bool:
        """Initialize analytics database without auto-population"""
        try:
            import analytics_core
            
            # Remove existing analytics.db to ensure clean start
            analytics_db_path = os.path.join(self.base_dir, "analytics.db")
            if os.path.exists(analytics_db_path):
                os.remove(analytics_db_path)
                logger.info("🗑️  Removed existing analytics.db")
            
            # Create analytics instance WITHOUT triggering auto-population
            analytics = analytics_core.AnalyticsCore()
            self.log_init("Analytics database (analytics.db)", "success", "and empty")
            return True
        except Exception as e:
            self.log_init("Analytics database", "error", str(e))
            return False
    
    def init_rag_databases(self) -> bool:
        """Initialize RAG databases"""
        try:
            # Remove existing rag_app.db for clean start
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
                create_document_store()
                self.log_init("RAG databases", "success", "and empty")
                return True
            else:
                logger.warning("⚠️  RAG API module not found, skipping RAG databases")
                return True
        except Exception as e:
            self.log_init("RAG databases", "error", str(e))
            return False
    
    def clean_database_files(self) -> bool:
        """Remove all existing database files"""
        try:
            # List of database files to remove
            db_files = [
                "users.db", "metrics.db", "reports.db", "analytics.db", "rag_app.db",
                "api_keys.db"
            ]
            
            # Remove database files in graphtalk directory
            for db_file in db_files:
                db_path = os.path.join(self.base_dir, db_file)
                if os.path.exists(db_path):
                    os.remove(db_path)
                    logger.info(f"🗑️  Removed existing {db_file}")
            
            # Remove database files in data directory
            data_dir = os.path.join(self.base_dir, "data")
            if os.path.exists(data_dir):
                for db_file in os.listdir(data_dir):
                    if db_file.endswith('.db'):
                        db_path = os.path.join(data_dir, db_file)
                        os.remove(db_path)
                        logger.info(f"🗑️  Removed existing data/{db_file}")
            
            # Remove database files in integration_toolkit
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
            directories = [
                "data", "uploads", "chroma_db"
            ]
            
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
    
    def verify_databases(self) -> bool:
        """Verify all databases are properly initialized"""
        try:
            verification_results = {}
            
            # Verify user database
            if os.path.exists("users.db"):
                conn = sqlite3.connect("users.db")
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM users")
                user_count = cursor.fetchone()[0]
                verification_results["users"] = user_count
                conn.close()
            
            # Verify metrics database
            if os.path.exists("metrics.db"):
                conn = sqlite3.connect("metrics.db")
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                verification_results["metrics_tables"] = tables
                conn.close()
            
            # Verify analytics database
            if os.path.exists("analytics.db"):
                import analytics_core
                analytics = analytics_core.AnalyticsCore()
                daily_data = analytics.get_daily_query_volume(days=7)
                verification_results["analytics_rows"] = len(daily_data)
            
            # Log verification results
            logger.info("📋 Database verification results:")
            for key, value in verification_results.items():
                logger.info(f"  📄 {key}: {value}")
            
            return True
        except Exception as e:
            logger.error(f"❌ Database verification failed: {e}")
            return False
    
    def get_database_summary(self) -> dict:
        """Get summary of all database files"""
        summary = {}
        
        # Check all database files
        for root, dirs, files in os.walk(self.base_dir):
            for file in files:
                if file.endswith('.db'):
                    file_path = os.path.join(root, file)
                    size = os.path.getsize(file_path)
                    rel_path = os.path.relpath(file_path, self.base_dir)
                    summary[rel_path] = size
        
        return summary
    
    async def initialize_all(self, clean: bool = True) -> bool:
        """Initialize all databases"""
        logger.info("🚀 Starting unified database initialization...")
        
        try:
            # Step 1: Clean existing files and directories
            if clean:
                logger.info("🧹 Cleaning existing databases and directories...")
                if not self.clean_database_files():
                    return False
                if not self.clean_directories():
                    return False
            
            # Step 2: Ensure required directories
            logger.info("📁 Ensuring required directories...")
            if not self.ensure_directory("data"):
                return False
            if not self.ensure_directory("uploads"):
                return False
            if not self.ensure_directory("chroma_db"):
                return False
            
            # Step 3: Initialize all databases
            logger.info("🔧 Initializing databases...")
            
            init_functions = [
                ("User Database", self.init_user_database),
                ("Metrics Database", self.init_metrics_database),
                ("Reports Database", self.init_reports_database),
                ("Plugins Database", self.init_plugins_database),
                ("API Keys Database", self.init_api_keys_database),
                ("OpenCart Database", self.init_opencart_database),
                ("Analytics Database", self.init_analytics_database),
                ("RAG Databases", self.init_rag_databases),
            ]
            
            for db_name, init_func in init_functions:
                logger.info(f"🔧 Initializing {db_name}...")
                if not init_func():
                    return False
            
            # Step 4: Verify initialization
            logger.info("🔍 Verifying database initialization...")
            if not self.verify_databases():
                return False
            
            # Step 5: Show summary
            logger.info("📋 Database initialization summary:")
            summary = self.get_database_summary()
            for db_path, size in sorted(summary.items()):
                logger.info(f"  📄 {db_path} ({size} bytes)")
            
            logger.info("🎉 All databases initialized successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
            return False


async def main():
    """Main initialization function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Unified Database Initialization for WikiAI")
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
    
    initializer = DatabaseInitializer()
    
    if args.verify_only:
        logger.info("🔍 Verifying existing databases only...")
        initializer.verify_databases()
        summary = initializer.get_database_summary()
        logger.info("📋 Current database files:")
        for db_path, size in sorted(summary.items()):
            logger.info(f"  📄 {db_path} ({size} bytes)")
    else:
        clean = not args.no_clean
        success = await initializer.initialize_all(clean=clean)
        if not success:
            sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Database initialization interrupted")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
