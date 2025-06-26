import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import requests
import os
from pathlib import Path

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# User session data storage
user_data = {}

# States for conversation handling
(
    SETTING_SERVER_URL,
    ENTERING_TOKEN,
    QUERY_KB,
    UPLOAD_KB,
    VIEW_DOCS,
) = range(5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user_id = update.effective_user.id
    user_data[user_id] = {
        'server_url': '',
        'token': '',
        'server_connected': False,
        'token_created': False
    }
    
    keyboard = [
        [InlineKeyboardButton("Set Server URL", callback_data=str(SETTING_SERVER_URL))],
        [InlineKeyboardButton("Enter/Create Token", callback_data=str(ENTERING_TOKEN))],
        [InlineKeyboardButton("Query Knowledge Base", callback_data=str(QUERY_KB))],
        [InlineKeyboardButton("Upload Knowledge Base", callback_data=str(UPLOAD_KB))],
        [InlineKeyboardButton("View Documentation", callback_data=str(VIEW_DOCS))],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Welcome to SC-Machine Telegram Client!\n\n"
        "Please select an option:",
        reply_markup=reply_markup
    )

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button presses from the inline keyboard."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {
            'server_url': '',
            'token': '',
            'server_connected': False,
            'token_created': False
        }
    
    choice = int(query.data)
    
    if choice == SETTING_SERVER_URL:
        await query.edit_message_text(
            text="Please enter the server URL (e.g., http://localhost:9001):"
        )
        context.user_data['state'] = SETTING_SERVER_URL
    elif choice == ENTERING_TOKEN:
        keyboard = [
            [InlineKeyboardButton("Create New Token", callback_data='create_token')],
            [InlineKeyboardButton("Enter Existing Token", callback_data='enter_token')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text="Token Management:",
            reply_markup=reply_markup
        )
    elif choice == QUERY_KB:
        if not user_data[user_id]['server_connected']:
            await query.edit_message_text(
                text="Please connect to a server first using 'Set Server URL'"
            )
            return
        if not user_data[user_id]['token_created']:
            await query.edit_message_text(
                text="Please create or enter a token first using 'Enter/Create Token'"
            )
            return
            
        await query.edit_message_text(
            text="Please enter your query:"
        )
        context.user_data['state'] = QUERY_KB
    elif choice == UPLOAD_KB:
        if not user_data[user_id]['server_connected']:
            await query.edit_message_text(
                text="Please connect to a server first using 'Set Server URL'"
            )
            return
        if not user_data[user_id]['token_created']:
            await query.edit_message_text(
                text="Please create or enter a token first using 'Enter/Create Token'"
            )
            return
            
        await query.edit_message_text(
            text="Please upload a ZIP file containing the knowledge base:"
        )
        context.user_data['state'] = UPLOAD_KB
    elif choice == VIEW_DOCS:
        await show_documentation(query)
    elif query.data == 'create_token':
        await create_token(query, context)
    elif query.data == 'enter_token':
        await query.edit_message_text(
            text="Please enter your existing token:"
        )
        context.user_data['state'] = ENTERING_TOKEN

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages based on the current state."""
    user_id = update.effective_user.id
    if user_id not in user_data:
        user_data[user_id] = {
            'server_url': '',
            'token': '',
            'server_connected': False,
            'token_created': False
        }
    
    current_state = context.user_data.get('state', None)
    text = update.message.text
    
    if current_state == SETTING_SERVER_URL:
        user_data[user_id]['server_url'] = text.rstrip('/')
        # Test the connection
        try:
            await update.message.reply_text("Testing connection to server...")
            response = requests.get(f"{user_data[user_id]['server_url']}/")
            if response.status_code == 200:
                user_data[user_id]['server_connected'] = True
                await update.message.reply_text(
                    "Connected to server successfully!\n"
                    f"Server response: {response.json()}"
                )
            else:
                await update.message.reply_text(
                    f"Server returned status code {response.status_code}"
                )
        except requests.exceptions.RequestException as e:
            await update.message.reply_text(f"Failed to connect to server: {str(e)}")
        
        context.user_data['state'] = None
        await show_main_menu(update)
        
    elif current_state == ENTERING_TOKEN:
        user_data[user_id]['token'] = text
        user_data[user_id]['token_created'] = True
        await update.message.reply_text("Token saved successfully!")
        context.user_data['state'] = None
        await show_main_menu(update)
        
    elif current_state == QUERY_KB:
        await process_query(update, context, text)
        context.user_data['state'] = None
        await show_main_menu(update)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle document uploads for knowledge base."""
    user_id = update.effective_user.id
    if user_id not in user_data:
        user_data[user_id] = {
            'server_url': '',
            'token': '',
            'server_connected': False,
            'token_created': False
        }
    
    current_state = context.user_data.get('state', None)
    
    if current_state == UPLOAD_KB:
        document = update.message.document
        if document.mime_type != "application/zip":
            await update.message.reply_text("Please upload a ZIP file.")
            return
            
        # Download the file
        file = await context.bot.get_file(document.file_id)
        file_path = f"temp_{user_id}.zip"
        await file.download_to_drive(file_path)
        
        await update.message.reply_text("Uploading and processing knowledge base...")
        
        try:
            headers = {
                "Authorization": f"Bearer {user_data[user_id]['token']}"
            }
            with open(file_path, 'rb') as f:
                files = {
                    "file": (document.file_name, f, "application/zip")
                }
                response = requests.post(
                    f"{user_data[user_id]['server_url']}/upload/kb_zip",
                    files=files,
                    headers=headers
                )
            
            os.remove(file_path)
            
            if response.status_code == 200:
                data = response.json()
                if data['status'] == "success":
                    await update.message.reply_text(
                        "Knowledge base uploaded successfully!\n"
                        f"Response: {data['response']}"
                    )
                else:
                    await update.message.reply_text(f"Upload failed: {data['message']}")
            else:
                await update.message.reply_text(f"Server returned status code {response.status_code}")
        except requests.exceptions.RequestException as e:
            await update.message.reply_text(f"Failed to upload file: {str(e)}")
        
        context.user_data['state'] = None
        await show_main_menu(update)

async def create_token(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create a new token for the user."""
    user_id = query.from_user.id
    if not user_data[user_id]['server_connected']:
        await query.edit_message_text(
            text="Please connect to a server first using 'Set Server URL'"
        )
        return
    
    await query.edit_message_text(text="Creating token...")
    
    try:
        response = requests.post(f"{user_data[user_id]['server_url']}/create_token")
        if response.status_code == 200:
            data = response.json()
            if data['status'] == "success":
                user_data[user_id]['token'] = data['token']
                user_data[user_id]['token_created'] = True
                await query.edit_message_text(
                    text="Token created successfully! Copy this token now as it won't be shown again:\n"
                    f"`{data['token']}`\n\n"
                    "Use /menu to return to main menu.",
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text(text=f"Token creation failed: {data['message']}")
        else:
            await query.edit_message_text(text=f"Server returned status code {response.status_code}")
    except requests.exceptions.RequestException as e:
        await query.edit_message_text(text=f"Failed to create token: {str(e)}")

async def process_query(update: Update, context: ContextTypes.DEFAULT_TYPE, query_text: str) -> None:
    """Process a knowledge base query."""
    user_id = update.effective_user.id
    
    await update.message.reply_text("Processing query...")
    
    try:
        headers = {
            "Authorization": f"Bearer {user_data[user_id]['token']}"
        }
        payload = {
            "text": query_text
        }
        response = requests.post(
            f"{user_data[user_id]['server_url']}/query?humanize=true",
            json=payload,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            if data['status'] == "success":
                response_text = data['response']
                # Telegram has a message length limit, so we might need to split long responses
                if len(response_text) > 4096:
                    for x in range(0, len(response_text), 4096):
                        await update.message.reply_text(response_text[x:x+4096])
                else:
                    await update.message.reply_text(response_text)
            else:
                await update.message.reply_text(f"Query failed: {data['message']}")
        else:
            await update.message.reply_text(f"Server returned status code {response.status_code}")
    except requests.exceptions.RequestException as e:
        await update.message.reply_text(f"Failed to submit query: {str(e)}")

async def show_documentation(query) -> None:
    """Show the documentation from README.md or fallback content."""
    try:
        # Try to read README.md from the current directory
        readme_path = Path(__file__).parent / "README.md"
        with open(readme_path, "r", encoding="utf-8") as f:
            readme_content = f.read()
        
        # Telegram has a message length limit, so we might need to split the content
        if len(readme_content) > 4096:
            await query.edit_message_text(text=readme_content[:4096])
            remaining_text = readme_content[4096:]
            for x in range(0, len(remaining_text), 4096):
                await query._bot.send_message(
                    chat_id=query.message.chat_id,
                    text=remaining_text[x:x+4096]
                )
        else:
            await query.edit_message_text(text=readme_content)
    except FileNotFoundError:
        fallback_docs = """
        ## SC-Machine API
        
        This is a knowledge base query and management system that allows:
        
        - Querying a semantic knowledge base
        - Uploading new knowledge bases in zip format
        - Secure token-based authentication
        
        ### Endpoints
        
        - `POST /query`: Submit a query to the knowledge base
        - `POST /upload/kb_zip`: Upload a new knowledge base
        - `POST /create_token`: Generate an access token
        
        ### Authentication
        
        The API uses bearer token authentication. You need to:
        1. First create a token using `/create_token`
        2. Use this token in the `Authorization` header for all other requests
        """
        await query.edit_message_text(text=fallback_docs)

async def show_main_menu(update) -> None:
    """Show the main menu with options."""
    keyboard = [
        [InlineKeyboardButton("Set Server URL", callback_data=str(SETTING_SERVER_URL))],
        [InlineKeyboardButton("Enter/Create Token", callback_data=str(ENTERING_TOKEN))],
        [InlineKeyboardButton("Query Knowledge Base", callback_data=str(QUERY_KB))],
        [InlineKeyboardButton("Upload Knowledge Base", callback_data=str(UPLOAD_KB))],
        [InlineKeyboardButton("View Documentation", callback_data=str(VIEW_DOCS))],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if isinstance(update, Update):
        await update.message.reply_text(
            "Main Menu:",
            reply_markup=reply_markup
        )
    else:  # It's a CallbackQuery
        await update.edit_message_text(
            text="Main Menu:",
            reply_markup=reply_markup
        )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the main menu when /menu is called."""
    await show_main_menu(update)

def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token("").build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu))
    
    # Add callback query handler
    application.add_handler(CallbackQueryHandler(handle_button))
    
    # Add message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()