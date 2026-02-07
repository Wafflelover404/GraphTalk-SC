import aiosqlite
import os
import uuid
import json
import datetime
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel
from fastapi import HTTPException

DB_PATH = os.path.join(os.path.dirname(__file__), 'quiz.db')

class QuizQuestion(BaseModel):
    id: str
    type: str
    question: str
    options: Optional[List[str]] = None
    correct_answer: Union[str, int]
    explanation: Optional[str] = None
    points: int = 10

class Quiz(BaseModel):
    id: str
    title: str
    description: str
    category: str
    difficulty: str
    time_limit: int
    passing_score: int
    questions: List[QuizQuestion]
    created_at: str
    created_by: str
    organization_id: Optional[str] = None

class QuizSubmission(BaseModel):
    quiz_id: str
    user_id: str
    answers: Dict[str, str]
    score: int
    total_points: int
    passed: bool
    time_spent: int
    submitted_at: str

async def init_quiz_management_db():
    """Initialize quiz management tables"""
    async with aiosqlite.connect(DB_PATH) as conn:
        # Create managed quizzes table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS managed_quizzes (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                time_limit INTEGER NOT NULL,
                passing_score INTEGER NOT NULL,
                questions TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                organization_id TEXT,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')
        
        # Create quiz submissions table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS quiz_submissions (
                id TEXT PRIMARY KEY,
                quiz_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                answers TEXT NOT NULL,
                score INTEGER NOT NULL,
                total_points INTEGER NOT NULL,
                passed BOOLEAN NOT NULL,
                time_spent INTEGER NOT NULL,
                submitted_at TEXT NOT NULL,
                organization_id TEXT,
                FOREIGN KEY (quiz_id) REFERENCES managed_quizzes (id)
            )
        ''')
        
        # Create indexes
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_managed_quizzes_org ON managed_quizzes(organization_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_managed_quizzes_creator ON managed_quizzes(created_by)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_quiz_submissions_quiz ON quiz_submissions(quiz_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_quiz_submissions_user ON quiz_submissions(user_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_quiz_submissions_org ON quiz_submissions(organization_id)')
        
        await conn.commit()

async def create_manual_quiz(
    title: str,
    description: str,
    category: str,
    difficulty: str,
    time_limit: int,
    passing_score: int,
    questions: List[QuizQuestion],
    created_by: str,
    organization_id: Optional[str] = None
) -> str:
    """Create a manual quiz"""
    quiz_id = str(uuid.uuid4())
    created_at = datetime.datetime.utcnow().isoformat()
    
    # Validate questions
    if not questions:
        raise HTTPException(status_code=400, detail="Quiz must have at least one question")
    
    for i, q in enumerate(questions):
        if not q.question:
            raise HTTPException(status_code=400, detail=f"Question {i+1} cannot be empty")
        if not q.options or len(q.options) < 2:
            raise HTTPException(status_code=400, detail=f"Question {i+1} must have at least 2 options")
        if q.correct_answer not in q.options:
            raise HTTPException(status_code=400, detail=f"Question {i+1} answer must be one of the options")
    
    questions_json = json.dumps([q.dict() for q in questions])
    
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute('''
            INSERT INTO managed_quizzes 
            (id, title, description, category, difficulty, time_limit, passing_score, 
             questions, created_at, created_by, organization_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (quiz_id, title, description, category, difficulty, time_limit, passing_score,
              questions_json, created_at, created_by, organization_id))
        await conn.commit()
    
    return quiz_id

async def get_all_quizzes(
    organization_id: Optional[str] = None,
    created_by: Optional[str] = None,
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Quiz]:
    """Get all quizzes with optional filters"""
    async with aiosqlite.connect(DB_PATH) as conn:
        query = 'SELECT * FROM managed_quizzes WHERE is_active = TRUE'
        params = []
        
        if organization_id:
            query += ' AND organization_id = ?'
            params.append(organization_id)
        
        if created_by:
            query += ' AND created_by = ?'
            params.append(created_by)
        
        if category:
            query += ' AND category = ?'
            params.append(category)
        
        if difficulty:
            query += ' AND difficulty = ?'
            params.append(difficulty)
        
        query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        
        async with conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            
        quizzes = []
        for row in rows:
            questions_data = json.loads(row[7]) if row[7] else []
            questions = [QuizQuestion(**q) for q in questions_data]
            
            quiz = Quiz(
                id=row[0],
                title=row[1],
                description=row[2],
                category=row[3],
                difficulty=row[4],
                time_limit=row[5],
                passing_score=row[6],
                questions=questions,
                created_at=row[8],
                created_by=row[9],
                organization_id=row[10]
            )
            quizzes.append(quiz)
        
        return quizzes

async def get_quiz_by_id(quiz_id: str, organization_id: Optional[str] = None) -> Optional[Quiz]:
    """Get a specific quiz by ID"""
    async with aiosqlite.connect(DB_PATH) as conn:
        query = 'SELECT * FROM managed_quizzes WHERE id = ? AND is_active = TRUE'
        params = [quiz_id]
        
        if organization_id:
            query += ' AND organization_id = ?'
            params.append(organization_id)
        
        async with conn.execute(query, params) as cursor:
            row = await cursor.fetchone()
            
        if not row:
            return None
        
        questions_data = json.loads(row[7]) if row[7] else []
        questions = [QuizQuestion(**q) for q in questions_data]
        
        return Quiz(
            id=row[0],
            title=row[1],
            description=row[2],
            category=row[3],
            difficulty=row[4],
            time_limit=row[5],
            passing_score=row[6],
            questions=questions,
            created_at=row[8],
            created_by=row[9],
            organization_id=row[10]
        )

async def update_quiz(
    quiz_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    time_limit: Optional[int] = None,
    passing_score: Optional[int] = None,
    questions: Optional[List[QuizQuestion]] = None,
    organization_id: Optional[str] = None
) -> bool:
    """Update an existing quiz"""
    async with aiosqlite.connect(DB_PATH) as conn:
        # Check if quiz exists
        check_query = 'SELECT id FROM managed_quizzes WHERE id = ? AND is_active = TRUE'
        params = [quiz_id]
        
        if organization_id:
            check_query += ' AND organization_id = ?'
            params.append(organization_id)
        
        async with conn.execute(check_query, params) as cursor:
            if not await cursor.fetchone():
                return False
        
        # Build update query
        updates = []
        update_params = []
        
        if title is not None:
            updates.append('title = ?')
            update_params.append(title)
        
        if description is not None:
            updates.append('description = ?')
            update_params.append(description)
        
        if category is not None:
            updates.append('category = ?')
            update_params.append(category)
        
        if difficulty is not None:
            updates.append('difficulty = ?')
            update_params.append(difficulty)
        
        if time_limit is not None:
            updates.append('time_limit = ?')
            update_params.append(time_limit)
        
        if passing_score is not None:
            updates.append('passing_score = ?')
            update_params.append(passing_score)
        
        if questions is not None:
            questions_json = json.dumps([q.dict() for q in questions])
            updates.append('questions = ?')
            update_params.append(questions_json)
        
        if updates:
            query = f'UPDATE managed_quizzes SET {", ".join(updates)} WHERE id = ?'
            update_params.append(quiz_id)
            
            if organization_id:
                query += ' AND organization_id = ?'
                update_params.append(organization_id)
            
            await conn.execute(query, update_params)
            await conn.commit()
        
        return True

async def delete_quiz(quiz_id: str, organization_id: Optional[str] = None) -> bool:
    """Soft delete a quiz (set is_active = FALSE)"""
    async with aiosqlite.connect(DB_PATH) as conn:
        query = 'UPDATE managed_quizzes SET is_active = FALSE WHERE id = ?'
        params = [quiz_id]
        
        if organization_id:
            query += ' AND organization_id = ?'
            params.append(organization_id)
        
        cursor = await conn.execute(query, params)
        await conn.commit()
        
        return cursor.rowcount > 0

async def submit_quiz_result(
    quiz_id: str,
    user_id: str,
    answers: Dict[str, str],
    score: int,
    total_points: int,
    passed: bool,
    time_spent: int,
    organization_id: Optional[str] = None
) -> str:
    """Submit a quiz result"""
    submission_id = str(uuid.uuid4())
    submitted_at = datetime.datetime.utcnow().isoformat()
    
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute('''
            INSERT INTO quiz_submissions 
            (id, quiz_id, user_id, answers, score, total_points, passed, time_spent, submitted_at, organization_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (submission_id, quiz_id, user_id, json.dumps(answers), score, total_points,
              passed, time_spent, submitted_at, organization_id))
        await conn.commit()
    
    return submission_id

async def get_quiz_submissions(
    quiz_id: Optional[str] = None,
    user_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[QuizSubmission]:
    """Get quiz submissions with optional filters"""
    async with aiosqlite.connect(DB_PATH) as conn:
        query = 'SELECT * FROM quiz_submissions'
        params = []
        conditions = []
        
        if quiz_id:
            conditions.append('quiz_id = ?')
            params.append(quiz_id)
        
        if user_id:
            conditions.append('user_id = ?')
            params.append(user_id)
        
        if organization_id:
            conditions.append('organization_id = ?')
            params.append(organization_id)
        
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        
        query += ' ORDER BY submitted_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        
        async with conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        
        submissions = []
        for row in rows:
            submission = QuizSubmission(
                quiz_id=row[1],
                user_id=row[2],
                answers=json.loads(row[3]) if row[3] else {},
                score=row[4],
                total_points=row[5],
                passed=bool(row[6]),
                time_spent=row[7],
                submitted_at=row[8]
            )
            submissions.append(submission)
        
        return submissions

async def get_quiz_statistics(quiz_id: str, organization_id: Optional[str] = None) -> Dict[str, Any]:
    """Get statistics for a specific quiz"""
    async with aiosqlite.connect(DB_PATH) as conn:
        query = '''
            SELECT 
                COUNT(*) as total_submissions,
                COUNT(*) FILTER (WHERE passed = TRUE) as passed_submissions,
                AVG(score) as avg_score,
                AVG(time_spent) as avg_time_spent,
                MAX(score) as max_score,
                MIN(score) as min_score
            FROM quiz_submissions 
            WHERE quiz_id = ?
        '''
        params = [quiz_id]
        
        if organization_id:
            query += ' AND organization_id = ?'
            params.append(organization_id)
        
        async with conn.execute(query, params) as cursor:
            row = await cursor.fetchone()
        
        if not row:
            return {
                "total_submissions": 0,
                "passed_submissions": 0,
                "pass_rate": 0,
                "avg_score": 0,
                "avg_time_spent": 0,
                "max_score": 0,
                "min_score": 0
            }
        
        total_submissions = row[0] or 0
        passed_submissions = row[1] or 0
        pass_rate = (passed_submissions / total_submissions * 100) if total_submissions > 0 else 0
        
        return {
            "total_submissions": total_submissions,
            "passed_submissions": passed_submissions,
            "pass_rate": round(pass_rate, 2),
            "avg_score": round(row[2] or 0, 2),
            "avg_time_spent": round(row[3] or 0, 2),
            "max_score": row[4] or 0,
            "min_score": row[5] or 0
        }
