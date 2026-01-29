import aiosqlite
import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "landing_pages.db")

async def init_database():
    """Initialize all database tables"""
    logger.info("Initializing database...")
    
    async with aiosqlite.connect(DATABASE_URL) as db:
        # Enable foreign keys
        await db.execute("PRAGMA foreign_keys = ON")
        
        # Blog posts table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS blog_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                excerpt TEXT,
                content TEXT NOT NULL,
                author TEXT NOT NULL,
                category TEXT NOT NULL,
                featured BOOLEAN DEFAULT FALSE,
                tags TEXT, -- JSON array
                image_url TEXT,
                read_time TEXT,
                views INTEGER DEFAULT 0,
                status TEXT DEFAULT 'draft', -- draft, published, archived
                published_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Blog categories table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS blog_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                description TEXT,
                color TEXT DEFAULT '#3b82f6',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Newsletter subscriptions
        await db.execute("""
            CREATE TABLE IF NOT EXISTS newsletter_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                status TEXT DEFAULT 'active', -- active, unsubscribed, bounced
                preferences TEXT, -- JSON object
                source TEXT DEFAULT 'website', -- website, import, manual
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Contact submissions
        await db.execute("""
            CREATE TABLE IF NOT EXISTS contact_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                company TEXT,
                phone TEXT,
                message TEXT NOT NULL,
                inquiry_type TEXT DEFAULT 'general', -- general, sales, support, partnership
                status TEXT DEFAULT 'new', -- new, in_progress, resolved, closed
                priority TEXT DEFAULT 'medium', -- low, medium, high, urgent
                assigned_to TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Demo requests
        await db.execute("""
            CREATE TABLE IF NOT EXISTS demo_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                company TEXT NOT NULL,
                phone TEXT,
                job_title TEXT,
                company_size TEXT,
                industry TEXT,
                preferred_time TEXT,
                preferred_date DATE,
                message TEXT,
                status TEXT DEFAULT 'new', -- new, scheduled, completed, cancelled
                assigned_to TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Sales leads
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sales_leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                company TEXT,
                phone TEXT,
                source TEXT DEFAULT 'website', -- website, referral, cold_call, etc.
                status TEXT DEFAULT 'new', -- new, contacted, qualified, proposal, closed_won, closed_lost
                score INTEGER DEFAULT 0,
                assigned_to TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Quote requests
        await db.execute("""
            CREATE TABLE IF NOT EXISTS quote_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                contact_email TEXT NOT NULL,
                contact_name TEXT,
                phone TEXT,
                requirements TEXT,
                user_count INTEGER,
                current_solution TEXT,
                budget_range TEXT,
                timeline TEXT,
                status TEXT DEFAULT 'new', -- new, preparing, sent, accepted, rejected
                quote_amount DECIMAL(10,2),
                valid_until DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Help articles
        await db.execute("""
            CREATE TABLE IF NOT EXISTS help_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                description TEXT,
                content TEXT NOT NULL,
                category TEXT NOT NULL,
                views INTEGER DEFAULT 0,
                helpful_count INTEGER DEFAULT 0,
                total_votes INTEGER DEFAULT 0,
                read_time TEXT,
                difficulty TEXT DEFAULT 'beginner', -- beginner, intermediate, advanced
                order_index INTEGER DEFAULT 0,
                status TEXT DEFAULT 'draft', -- draft, published, archived
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Help categories
        await db.execute("""
            CREATE TABLE IF NOT EXISTS help_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                description TEXT,
                icon TEXT,
                order_index INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Video tutorials
        await db.execute("""
            CREATE TABLE IF NOT EXISTS video_tutorials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                video_url TEXT,
                thumbnail_url TEXT,
                duration TEXT,
                category TEXT,
                views INTEGER DEFAULT 0,
                status TEXT DEFAULT 'draft', -- draft, published
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Status incidents
        await db.execute("""
            CREATE TABLE IF NOT EXISTS status_incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                severity TEXT DEFAULT 'minor', -- critical, major, minor, maintenance
                status TEXT DEFAULT 'investigating', -- investigating, identified, monitoring, resolved
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                affected_services TEXT, -- JSON array
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Service status
        await db.execute("""
            CREATE TABLE IF NOT EXISTS service_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'operational', -- operational, degraded, down, maintenance
                uptime_percentage DECIMAL(5,2) DEFAULT 99.9,
                last_checked TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Documentation
        await db.execute("""
            CREATE TABLE IF NOT EXISTS documentation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                content TEXT NOT NULL,
                category TEXT NOT NULL,
                difficulty TEXT DEFAULT 'beginner',
                read_time TEXT,
                order_index INTEGER DEFAULT 0,
                status TEXT DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Analytics events
        await db.execute("""
            CREATE TABLE IF NOT EXISTS analytics_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL, -- page_view, conversion, download, etc.
                page TEXT,
                user_id TEXT,
                session_id TEXT,
                ip_address TEXT,
                user_agent TEXT,
                referrer TEXT,
                utm_source TEXT,
                utm_medium TEXT,
                utm_campaign TEXT,
                metadata TEXT, -- JSON object
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Landing page visits
        await db.execute("""
            CREATE TABLE IF NOT EXISTS landing_page_visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                page TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                referrer TEXT,
                utm_source TEXT,
                utm_medium TEXT,
                utm_campaign TEXT,
                session_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for better performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_blog_posts_status ON blog_posts(status)",
            "CREATE INDEX IF NOT EXISTS idx_blog_posts_category ON blog_posts(category)",
            "CREATE INDEX IF NOT EXISTS idx_blog_posts_featured ON blog_posts(featured)",
            "CREATE INDEX IF NOT EXISTS idx_contact_submissions_status ON contact_submissions(status)",
            "CREATE INDEX IF NOT EXISTS idx_demo_requests_status ON demo_requests(status)",
            "CREATE INDEX IF NOT EXISTS idx_sales_leads_status ON sales_leads(status)",
            "CREATE INDEX IF NOT EXISTS idx_help_articles_category ON help_articles(category)",
            "CREATE INDEX IF NOT EXISTS idx_help_articles_status ON help_articles(status)",
            "CREATE INDEX IF NOT EXISTS idx_status_incidents_status ON status_incidents(status)",
            "CREATE INDEX IF NOT EXISTS idx_analytics_events_type ON analytics_events(event_type)",
            "CREATE INDEX IF NOT EXISTS idx_analytics_events_created_at ON analytics_events(created_at)",
        ]
        
        for index_sql in indexes:
            await db.execute(index_sql)
        
        await db.commit()
    
    # Insert default data
    await insert_default_data()
    
    logger.info("Database initialized successfully")

async def insert_default_data():
    """Insert default categories and initial data"""
    async with aiosqlite.connect(DATABASE_URL) as db:
        # Default blog categories
        blog_categories = [
            ("AI & ML", "ai-ml", "Artificial Intelligence and Machine Learning topics", "#8b5cf6"),
            ("Product Updates", "product-updates", "Latest product features and updates", "#3b82f6"),
            ("Tutorials", "tutorials", "How-to guides and tutorials", "#10b981"),
            ("Company News", "company-news", "Company announcements and news", "#f59e0b"),
        ]
        
        for name, slug, desc, color in blog_categories:
            await db.execute("""
                INSERT OR IGNORE INTO blog_categories (name, slug, description, color)
                VALUES (?, ?, ?, ?)
            """, (name, slug, desc, color))
        
        # Default help categories
        help_categories = [
            ("Getting Started", "getting-started", "Basic setup and onboarding", "zap"),
            ("Account & Billing", "account-billing", "Account management and billing", "users"),
            ("Features", "features", "Feature guides and explanations", "book-open"),
            ("Technical Support", "technical-support", "Technical troubleshooting", "shield"),
        ]
        
        for name, slug, desc, icon in help_categories:
            await db.execute("""
                INSERT OR IGNORE INTO help_categories (name, slug, description, icon)
                VALUES (?, ?, ?, ?)
            """, (name, slug, desc, icon))
        
        # Default services for status monitoring
        services = [
            ("API Services", "Core API endpoints and authentication", "operational", 99.9),
            ("Database", "Primary and replica database clusters", "operational", 99.95),
            ("Search Engine", "Semantic search and indexing services", "operational", 99.8),
            ("AI Processing", "AI model inference and processing", "operational", 99.7),
            ("File Storage", "Document upload and storage services", "operational", 99.9),
            ("Authentication", "User authentication and authorization", "operational", 99.99),
        ]
        
        for name, desc, status, uptime in services:
            await db.execute("""
                INSERT OR IGNORE INTO service_status (name, description, status, uptime_percentage)
                VALUES (?, ?, ?, ?)
            """, (name, desc, status, uptime))
        
        await db.commit()
        logger.info("Default data inserted successfully")

# Database utility functions
async def get_db_connection():
    """Get database connection"""
    return await aiosqlite.connect(DATABASE_URL)

def dict_factory(cursor, row):
    """Convert row to dictionary"""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
