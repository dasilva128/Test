import logging
import os
from enum import Enum
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from github.GithubException import GithubException
from config import ALLOWED_USER_IDS

# Logging configuration
logging.basicConfig(
    filename='bot.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class UserState(Enum):
    IDLE = "idle"
    WAITING_FOR_REPO_NAME = "waiting_for_repo_name"
    WAITING_FOR_SET_REPO = "waiting_for_set_repo"
    WAITING_FOR_FILE_COUNT = "waiting_for_file_count"
    WAITING_FOR_UPLOAD_PATH = "waiting_for_upload_path"
    WAITING_FOR_FILES = "waiting_for_files"
    WAITING_FOR_DELETE = "waiting_for_delete"
    WAITING_FOR_BRANCH_NAME = "waiting_for_branch_name"
    WAITING_FOR_PR_DETAILS = "waiting_for_pr_details"
    WAITING_FOR_FOLDER_PATH = "waiting_for_folder_path"
    WAITING_FOR_DELETE_REPO = "waiting_for_delete_repo"
    WAITING_FOR_PRIVACY = "waiting_for_privacy"  # حالت جدید برای انتخاب پرایوت/پابلیک

class TelegramHandlers:
    def __init__(self, github_manager):
        self.github_manager = github_manager
        self.user_state = UserState.IDLE
        self.user_data = {}
        self.pending_uploads = []
        self.pending_deletes = []
        self.pending_repo_delete = None
        logger.debug("TelegramHandlers initialized")

    def get_main_menu(self):
        keyboard = [
            [InlineKeyboardButton("Create Repository", callback_data="create_repo"),
             InlineKeyboardButton("Set Repository", callback_data="set_repo")],
            [InlineKeyboardButton("Upload Files/Folder", callback_data="upload"),
             InlineKeyboardButton("Delete Files/Folder", callback_data="delete")],
            [InlineKeyboardButton("Create Branch", callback_data="branch"),
             InlineKeyboardButton("Create PR", callback_data="create_pr")],
            [InlineKeyboardButton("Fork Repository", callback_data="fork"),
             InlineKeyboardButton("List Managed Repos", callback_data="list_repos")],
            [InlineKeyboardButton("List All Repos", callback_data="list_all_repos"),
             InlineKeyboardButton("List Files", callback_data="list_files")],
            [InlineKeyboardButton("Delete Repository", callback_data="delete_repo")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def reset_state(self):
        logger.debug(f"Resetting user state. Current pending_deletes: {self.pending_deletes}, pending_repo_delete: {self.pending_repo_delete}")
        for file_path, _ in self.pending_uploads:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.debug(f"Temporary file {file_path} deleted")
                except Exception as e:
                    logger.error(f"Error deleting temporary file {file_path}: {str(e)}")
        self.user_state = UserState.IDLE
        self.user_data.clear()
        self.pending_uploads.clear()
        self.pending_deletes.clear()
        self.pending_repo_delete = None
        logger.debug("State reset completed")

    async def restrict_access(self, func, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in ALLOWED_USER_IDS:
            logger.warning(f"Unauthorized access attempt by user {user_id}")
            await update.message.reply_text("You are not authorized to use this bot!")
            return
        logger.debug(f"Authorized access for user {user_id}")
        return await func(update, context)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.debug("Executing /start command")
        self.reset_state()
        await update.message.reply_text("Welcome to the GitHub Bot! Choose an option:", reply_markup=self.get_main_menu())

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        action = query.data
        logger.debug(f"Button callback received: {action}, pending_deletes: {self.pending_deletes}, pending_repo_delete: {self.pending_repo_delete}")

        if action == "main_menu":
            self.reset_state()
            await query.message.reply_text("Main menu:", reply_markup=self.get_main_menu())
            return

        if action == "create_repo":
            self.user_state = UserState.WAITING_FOR_REPO_NAME
            await query.message.reply_text("Please enter the new repository name (e.g., test-repo):")
        elif action == "set_repo":
            self.user_state = UserState.WAITING_FOR_SET_REPO
            repos = self.github_manager.list_all_repositories()
            if "No repositories found" in repos or "Error" in repos:
                await query.message.reply_text(repos, reply_markup=self.get_main_menu())
                self.reset_state()
                return
            repo_list = repos.split('\n')
            keyboard = [
                [InlineKeyboardButton(repo.strip('- '), callback_data=f"select_repo_{repo.strip('- ')}")]
                for repo in repo_list
            ]
            keyboard.append([InlineKeyboardButton("Cancel", callback_data="main_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text("Please select a repository:", reply_markup=reply_markup)
        elif action.startswith("select_repo_"):
            repo_name = action[len("select_repo_"):]
            result = self.github_manager.set_repository(repo_name)
            await query.message.reply_text(result, reply_markup=self.get_main_menu())
            self.reset_state()
        elif action == "upload":
            self.user_state = UserState.WAITING_FOR_FILE_COUNT
            await query.message.reply_text("Please enter the number of files or 'folder' to upload a folder:")
        elif action == "delete":
            if not self.github_manager.current_repo:
                self.reset_state()
                await query.message.reply_text("Please select a repository first or create a new one.", reply_markup=self.get_main_menu())
                return
            self.user_state = UserState.WAITING_FOR_DELETE
            result, _ = self.github_manager.list_files()
            await query.message.reply_text(f"Please enter the file/folder path or number from the list to delete (e.g., 'docs/file.txt' or '1'):\n{result}")
        elif action == "branch":
            self.user_state = UserState.WAITING_FOR_BRANCH_NAME
            await query.message.reply_text("Please enter the new branch name (e.g., new-branch):")
        elif action == "create_pr":
            self.user_state = UserState.WAITING_FOR_PR_DETAILS
            await query.message.reply_text("Please enter the PR title and branch name (e.g., My PR new-branch):")
        elif action == "fork":
            result = self.github_manager.create_fork()
            self.reset_state()
            await query.message.reply_text(result, reply_markup=self.get_main_menu())
        elif action == "list_repos":
            result = self.github_manager.list_repositories()
            self.reset_state()
            await query.message.reply_text(result, reply_markup=self.get_main_menu())
        elif action == "list_all_repos":
            result = self.github_manager.list_all_repositories()
            self.reset_state()
            await query.message.reply_text(result, reply_markup=self.get_main_menu())
        elif action == "list_files":
            result, _ = self.github_manager.list_files()
            self.reset_state()
            await query.message.reply_text(result, reply_markup=self.get_main_menu())
        elif action == "delete_repo":
            self.user_state = UserState.WAITING_FOR_DELETE_REPO
            repos = self.github_manager.list_all_repositories()
            await query.message.reply_text(f"Please enter the repository name to delete (e.g., username/repo):\n{repos}")
        elif action == "confirm_delete":
            logger.debug(f"Confirm delete called with pending_deletes: {self.pending_deletes}")
            if self.pending_deletes:
                results = []
                for repo_path in self.pending_deletes:
                    logger.debug(f"Deleting path: {repo_path}")
                    result = self.github_manager.delete_path(repo_path)
                    results.append(result)
                await query.message.reply_text("Deletion successful:\n" + "\n".join(results), reply_markup=self.get_main_menu())
            else:
                await query.message.reply_text("No files/folders pending for deletion!", reply_markup=self.get_main_menu())
            self.reset_state()
        elif action == "cancel_delete":
            logger.debug("Cancel delete called")
            await query.message.reply_text("Deletion cancelled.", reply_markup=self.get_main_menu())
            self.reset_state()
        elif action == "confirm_delete_repo":
            logger.debug(f"Confirm delete repo called with pending_repo_delete: {self.pending_repo_delete}")
            if self.pending_repo_delete:
                result = self.github_manager.delete_repository(self.pending_repo_delete)
                await query.message.reply_text(result, reply_markup=self.get_main_menu())
            else:
                await query.message.reply_text("No repository pending for deletion!", reply_markup=self.get_main_menu())
            self.reset_state()
        elif action == "cancel_delete_repo":
            logger.debug("Cancel delete repo called")
            await query.message.reply_text("Repository deletion cancelled.", reply_markup=self.get_main_menu())
            self.reset_state()
        elif action == "confirm_upload":
            if self.pending_uploads:
                results = []
                for file_path, repo_path in self.pending_uploads:
                    result = self.github_manager.upload_file(file_path, repo_path)
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                            logger.debug(f"Temporary file {file_path} deleted")
                        except Exception as e:
                            logger.error(f"Error deleting temporary file {file_path}: {str(e)}")
                    results.append(result)
                await query.message.reply_text("Upload successful:\n" + "\n".join(results), reply_markup=self.get_main_menu())
            else:
                await query.message.reply_text("No files pending for upload!", reply_markup=self.get_main_menu())
            self.reset_state()
        elif action == "cancel_upload":
            await query.message.reply_text("Upload cancelled.", reply_markup=self.get_main_menu())
            self.reset_state()
        elif action == "privacy_public":
            repo_name = self.user_data.get("repo_name", "")
            if repo_name:
                result = self.github_manager.create_repository(repo_name, private=False)
                await query.message.reply_text(result, reply_markup=self.get_main_menu())
            else:
                await query.message.reply_text("Error: Repository name not found!", reply_markup=self.get_main_menu())
            self.reset_state()
        elif action == "privacy_private":
            repo_name = self.user_data.get("repo_name", "")
            if repo_name:
                result = self.github_manager.create_repository(repo_name, private=True)
                await query.message.reply_text(result, reply_markup=self.get_main_menu())
            else:
                await query.message.reply_text("Error: Repository name not found!", reply_markup=self.get_main_menu())
            self.reset_state()

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        logger.debug(f"Received text message: {text}, current state: {self.user_state}, pending_deletes: {self.pending_deletes}, pending_repo_delete: {self.pending_repo_delete}")

        if self.user_state == UserState.WAITING_FOR_REPO_NAME:
            self.user_data["repo_name"] = text
            self.user_state = UserState.WAITING_FOR_PRIVACY
            keyboard = [
                [InlineKeyboardButton("Public", callback_data="privacy_public"),
                 InlineKeyboardButton("Private", callback_data="privacy_private")],
                [InlineKeyboardButton("Cancel", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"Do you want the repository '{text}' to be public or private?", reply_markup=reply_markup)
        elif self.user_state == UserState.WAITING_FOR_SET_REPO:
            result = self.github_manager.set_repository(text)
            await update.message.reply_text(result, reply_markup=self.get_main_menu())
            self.reset_state()
        elif self.user_state == UserState.WAITING_FOR_FILE_COUNT:
            if text.lower() == "folder":
                self.user_state = UserState.WAITING_FOR_FOLDER_PATH
                await update.message.reply_text("Please enter the local folder path to upload (e.g., /path/to/folder):")
            elif not text.isdigit():
                await update.message.reply_text("Please enter a valid number (e.g., 2) or 'folder' for folder upload:", reply_markup=self.get_main_menu())
                self.reset_state()
                return
            else:
                file_count = int(text)
                if file_count <= 0:
                    await update.message.reply_text("Number of files must be greater than zero.", reply_markup=self.get_main_menu())
                    self.reset_state()
                    return
                if not self.github_manager.current_repo:
                    await update.message.reply_text("Please select a repository first or create a new one.", reply_markup=self.get_main_menu())
                    self.reset_state()
                    return
                self.user_state = UserState.WAITING_FOR_UPLOAD_PATH
                self.user_data = {"file_count": file_count}
                await update.message.reply_text("Please enter the upload path (e.g., folder/subfolder, or 'root' for root):")
        elif self.user_state == UserState.WAITING_FOR_UPLOAD_PATH:
            upload_path = text.strip('/')
            if upload_path.lower() == 'root':
                upload_path = ""
            logger.debug("Upload path set to repository root")
            self.user_data["upload_path"] = upload_path
            self.user_data["received_count"] = 0
            self.user_data["files"] = []
            self.user_state = UserState.WAITING_FOR_FILES
            await update.message.reply_text(f"Please send the first file of {self.user_data['file_count']}.")
        elif self.user_state == UserState.WAITING_FOR_FOLDER_PATH:
            folder_path = text.strip('/')
            if not os.path.isdir(folder_path):
                await update.message.reply_text(f"Error: {folder_path} is not a valid directory.", reply_markup=self.get_main_menu())
                self.reset_state()
                return
            self.user_state = UserState.WAITING_FOR_UPLOAD_PATH
            self.user_data["folder_path"] = folder_path
            await update.message.reply_text("Please enter the upload path (e.g., folder/subfolder, or 'root' for root):")
        elif self.user_state == UserState.WAITING_FOR_DELETE:
            if not self.github_manager.current_repo:
                await update.message.reply_text("Please select a repository first or create a new one.", reply_markup=self.get_main_menu())
                self.reset_state()
                return
            try:
                # Check if input is a number (index) or a path
                file_list_text, file_list = self.github_manager.list_files()
                if text.isdigit():
                    index = int(text)
                    if 1 <= index <= len(file_list):
                        repo_path = file_list[index - 1]
                        self.pending_deletes = [repo_path]
                        logger.debug(f"Pending deletes set: {self.pending_deletes}")
                        keyboard = [
                            [InlineKeyboardButton("Confirm", callback_data="confirm_delete"),
                             InlineKeyboardButton("Cancel", callback_data="cancel_delete")]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await update.message.reply_text(
                            f"Do you want to delete '{repo_path}'?",
                            reply_markup=reply_markup
                        )
                        self.user_state = UserState.IDLE
                    else:
                        await update.message.reply_text(
                            f"Invalid number {index}. Please select a valid number from the list:\n{file_list_text}",
                            reply_markup=self.get_main_menu()
                        )
                        self.reset_state()
                else:
                    repo_path = text.strip('/')
                    if repo_path.lower() == 'root':
                        repo_path = ""
                    logger.debug(f"Attempting to validate path: {repo_path}")
                    try:
                        # Validate path existence
                        self.github_manager.current_repo.get_contents(repo_path)
                        self.pending_deletes = [repo_path]
                        logger.debug(f"Pending deletes set: {self.pending_deletes}")
                        keyboard = [
                            [InlineKeyboardButton("Confirm", callback_data="confirm_delete"),
                             InlineKeyboardButton("Cancel", callback_data="cancel_delete")]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await update.message.reply_text(
                            f"Do you want to delete '{repo_path}'?",
                            reply_markup=reply_markup
                        )
                        self.user_state = UserState.IDLE
                    except GithubException as e:
                        logger.error(f"Error accessing path {repo_path}: {str(e)}")
                        await update.message.reply_text(
                            f"Error: Path '{repo_path}' not found in the repository! Available paths:\n{file_list_text}",
                            reply_markup=self.get_main_menu()
                        )
                        self.reset_state()
            except Exception as e:
                logger.error(f"Unexpected error in delete: {str(e)}")
                await update.message.reply_text(f"Error: {str(e)}", reply_markup=self.get_main_menu())
                self.reset_state()
        elif self.user_state == UserState.WAITING_FOR_BRANCH_NAME:
            branch_name = text
            result = self.github_manager.create_branch(branch_name)
            await update.message.reply_text(result, reply_markup=self.get_main_menu())
            self.reset_state()
        elif self.user_state == UserState.WAITING_FOR_PR_DETAILS:
            try:
                title, head_branch = text.split(maxsplit=1)
                result = self.github_manager.create_pull_request(title, "Created by bot", head_branch)
                await update.message.reply_text(result, reply_markup=self.get_main_menu())
                self.reset_state()
            except ValueError:
                await update.message.reply_text("Please enter the PR title and branch name correctly (e.g., My PR new-branch):", reply_markup=self.get_main_menu())
                self.reset_state()
        elif self.user_state == UserState.WAITING_FOR_DELETE_REPO:
            repo_name = text.strip()
            logger.debug(f"Received repository name for deletion: {repo_name}")
            try:
                repo = self.github_manager.user.get_repo(repo_name.split('/')[-1])
                self.pending_repo_delete = repo_name
                logger.debug(f"Pending repo delete set: {self.pending_repo_delete}")
                keyboard = [
                    [InlineKeyboardButton("Confirm", callback_data="confirm_delete_repo"),
                     InlineKeyboardButton("Cancel", callback_data="cancel_delete_repo")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    f"Are you sure you want to delete the repository '{repo_name}'? This action cannot be undone.",
                    reply_markup=reply_markup
                )
            except GithubException as e:
                logger.error(f"Error accessing repository {repo_name}: {str(e)}")
                await update.message.reply_text(
                    f"Error: Repository '{repo_name}' not found or inaccessible!", reply_markup=self.get_main_menu()
                )
                self.reset_state()

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.user_state != UserState.WAITING_FOR_FILES:
            logger.warning("File sent but not in file upload state")
            await update.message.reply_text("Please start the upload process from the main menu.", reply_markup=self.get_main_menu())
            self.reset_state()
            return

        file_count = self.user_data.get("file_count", 0)
        upload_path = self.user_data.get("upload_path", "")
        received_count = self.user_data.get("received_count", 0)
        files = self.user_data.get("files", [])
        document = update.message.document

        if not document:
            logger.warning("No file sent")
            await update.message.reply_text("Please send a file!", reply_markup=self.get_main_menu())
            self.reset_state()
            return

        received_count += 1
        file = await document.get_file()
        file_path = f"temp_{document.file_name}"
        repo_path = document.file_name if not upload_path else f"{upload_path}/{document.file_name}"

        try:
            await file.download_to_drive(file_path)
            files.append((file_path, repo_path))
            logger.debug(f"File {document.file_name} downloaded to temporary path {file_path}")
        except Exception as e:
            logger.error(f"Error downloading file {document.file_name}: {str(e)}")
            await update.message.reply_text(f"Error downloading file {document.file_name}: {str(e)}", reply_markup=self.get_main_menu())
            self.reset_state()
            return

        self.user_data["received_count"] = received_count
        self.user_data["files"] = files

        if received_count < file_count:
            remaining = file_count - received_count
            await update.message.reply_text(f"{remaining} file(s) remaining, please send the next file.")
        else:
            self.pending_uploads = files
            keyboard = [
                [InlineKeyboardButton("Confirm", callback_data="confirm_upload"),
                 InlineKeyboardButton("Cancel", callback_data="cancel_upload")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            path_text = "repository root" if not upload_path else f"path {upload_path}"
            await update.message.reply_text(
                f"Do you want to upload {file_count} file(s) to {path_text}?\n" +
                "\n".join([f"- {repo_path}" for _, repo_path in files]),
                reply_markup=reply_markup
            )
            self.user_data.clear()
            self.user_state = UserState.IDLE