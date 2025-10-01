# github_manager.py
import logging
from github import Github

# تنظیمات لاگ
logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GitHubManager:
    def __init__(self, token):
        """اتصال به GitHub"""
        logger.info("اتصال به GitHub با توکن")
        self.github = Github(token)
        self.user = self.github.get_user()
        self.repositories = {}
        self.current_repo = None

    def get_username(self):
        """دریافت نام کاربری GitHub"""
        username = self.user.login
        logger.info(f"نام کاربری GitHub دریافت شد: {username}")
        return username

    def set_repository(self, repo_name):
        """تنظیم مخزن فعلی"""
        logger.info(f"تلاش برای تنظیم مخزن: {repo_name}")
        try:
            self.current_repo = self.user.get_repo(repo_name.split('/')[-1])
            self.repositories[repo_name] = self.current_repo
            logger.info(f"مخزن {repo_name} با موفقیت تنظیم شد")
            return f"مخزن {repo_name} تنظیم شد."
        except Exception as e:
            logger.error(f"خطا در تنظیم مخزن {repo_name}: {str(e)}")
            return f"خطا: مخزن {repo_name} پیدا نشد! {str(e)}"

    def add_repository(self, repo_name):
        """اضافه کردن مخزن به لیست"""
        return self.set_repository(repo_name)

    def remove_repository(self, repo_name):
        """حذف مخزن از لیست مدیریت"""
        logger.info(f"تلاش برای حذف مخزن از لیست: {repo_name}")
        if repo_name in self.repositories:
            del self.repositories[repo_name]
            if self.current_repo and self.current_repo.full_name == repo_name:
                self.current_repo = None
            logger.info(f"مخزن {repo_name} از لیست مدیریت حذف شد")
            return f"مخزن {repo_name} از لیست مدیریت حذف شد."
        logger.warning(f"مخزن {repo_name} در لیست مدیریت یافت نشد")
        return f"خطا: مخزن {repo_name} در لیست نیست!"

    def delete_repository(self, repo_name):
        """حذف کامل مخزن از GitHub"""
        logger.info(f"تلاش برای حذف مخزن از GitHub: {repo_name}")
        try:
            repo = self.user.get_repo(repo_name.split('/')[-1])
            repo.delete()
            if repo_name in self.repositories:
                del self.repositories[repo_name]
            if self.current_repo and self.current_repo.full_name == repo_name:
                self.current_repo = None
            logger.info(f"مخزن {repo_name} از GitHub حذف شد")
            return f"مخزن {repo_name} از GitHub حذف شد."
        except Exception as e:
            logger.error(f"خطا در حذف مخزن {repo_name}: {str(e)}")
            return f"خطا در حذف مخزن: {str(e)}"

    def create_repository(self, repo_name, description="", private=False):
        """ایجاد مخزن جدید و تنظیم آن به‌عنوان مخزن فعلی"""
        logger.info(f"تلاش برای ایجاد مخزن جدید: {repo_name}")
        try:
            repo = self.user.create_repo(name=repo_name, description=description, private=private)
            self.repositories[repo.full_name] = repo
            self.current_repo = repo  # تنظیم مخزن جدید به‌عنوان مخزن فعلی
            logger.info(f"مخزن {repo_name} ایجاد شد و به‌عنوان مخزن فعلی تنظیم شد: {repo.html_url}")
            return f"مخزن {repo_name} ایجاد شد و به‌عنوان مخزن فعلی تنظیم شد: {repo.html_url}"
        except Exception as e:
            logger.error(f"خطا در ایجاد مخزن {repo_name}: {str(e)}")
            return f"خطا در ایجاد مخزن: {str(e)}"

    def list_repositories(self):
        """لیست کردن مخازن مدیریت‌شده"""
        logger.info("درخواست لیست مخازن مدیریت‌شده")
        if not self.repositories:
            logger.warning("هیچ مخزنی در لیست مدیریت وجود ندارد")
            return "هیچ مخزنی اضافه نشده است."
        repo_list = "\n".join([f"- {repo}" for repo in self.repositories.keys()])
        logger.info(f"لیست مخازن مدیریت‌شده: {repo_list}")
        return repo_list

    def list_all_repositories(self):
        """لیست تمام مخازن حساب GitHub"""
        logger.info("درخواست لیست تمام مخازن حساب GitHub")
        try:
            repos = self.user.get_repos()
            repo_list = "\n".join([f"- {repo.full_name}" for repo in repos])
            if not repo_list:
                logger.warning("هیچ مخزنی در حساب GitHub یافت نشد")
                return "هیچ مخزنی در حساب GitHub یافت نشد."
            logger.info(f"لیست تمام مخازن: {repo_list}")
            return repo_list
        except Exception as e:
            logger.error(f"خطا در دریافت لیست مخازن: {str(e)}")
            return f"خطا در دریافت لیست مخازن: {str(e)}"

    def upload_file(self, file_path, repo_path, commit_message="Upload via bot"):
        """آپلود یک فایل به مخزن فعلی"""
        logger.info(f"تلاش برای آپلود فایل به مسیر {repo_path}")
        if not self.current_repo:
            logger.error("هیچ مخزنی انتخاب نشده است")
            return "خطا: هیچ مخزنی انتخاب نشده است! از /set_repo استفاده کنید."
        try:
            with open(file_path, 'rb') as file:
                content = file.read()
            try:
                file_content = self.current_repo.get_contents(repo_path)
                self.current_repo.update_file(repo_path, commit_message, content, file_content.sha)
                logger.info(f"فایل {repo_path} به‌روزرسانی شد")
                return f"فایل {repo_path} به‌روزرسانی شد."
            except:
                self.current_repo.create_file(repo_path, commit_message, content)
                logger.info(f"فایل {repo_path} آپلود شد")
                return f"فایل {repo_path} آپلود شد."
        except Exception as e:
            logger.error(f"خطا در آپلود فایل به {repo_path}: {str(e)}")
            return f"خطا در آپلود فایل {repo_path}: {str(e)}"

    def delete_path(self, repo_path, commit_message="Delete via bot"):
        """حذف یک فایل یا پوشه از مخزن فعلی"""
        logger.info(f"تلاش برای حذف مسیر: {repo_path}")
        if not self.current_repo:
            logger.error("هیچ مخزنی انتخاب نشده است")
            return "خطا: هیچ مخزنی انتخاب نشده است!"
        try:
            contents = self.current_repo.get_contents(repo_path)
            if isinstance(contents, list):  # اگر پوشه باشد
                for content in contents:
                    self.current_repo.delete_file(content.path, commit_message, content.sha)
                    logger.info(f"فایل {content.path} از پوشه {repo_path} حذف شد")
                return f"پوشه {repo_path} و تمام محتوای آن حذف شد."
            else:  # اگر فایل باشد
                self.current_repo.delete_file(repo_path, commit_message, contents.sha)
                logger.info(f"فایل {repo_path} حذف شد")
                return f"فایل {repo_path} حذف شد."
        except Exception as e:
            logger.error(f"خطا در حذف مسیر {repo_path}: {str(e)}")
            return f"خطا در حذف مسیر {repo_path}: {str(e)}"

    def create_fork(self):
        """ایجاد فورک"""
        logger.info("تلاش برای ایجاد فورک")
        if not self.current_repo:
            logger.error("هیچ مخزنی انتخاب نشده است")
            return "خطا: هیچ مخزنی انتخاب نشده است!"
        try:
            fork = self.user.create_fork(self.current_repo)
            logger.info(f"فورک ایجاد شد: {fork.html_url}")
            return f"فورک ایجاد شد: {fork.html_url}"
        except Exception as e:
            logger.error(f"خطا در ایجاد فورک: {str(e)}")
            return f"خطا در فورک: {str(e)}"

    def create_branch(self, branch_name, source_branch="main"):
        """ایجاد شاخه جدید"""
        logger.info(f"تلاش برای ایجاد شاخه: {branch_name}")
        if not self.current_repo:
            logger.error("هیچ مخزنی انتخاب نشده است")
            return "خطا: هیچ مخزنی انتخاب نشده است!"
        try:
            source = self.current_repo.get_branch(source_branch)
            self.current_repo.create_git_ref(f"refs/heads/{branch_name}", source.commit.sha)
            logger.info(f"شاخه {branch_name} ایجاد شد")
            return f"شاخه {branch_name} ایجاد شد."
        except Exception as e:
            logger.error(f"خطا در ایجاد شاخه {branch_name}: {str(e)}")
            return f"خطا در ایجاد شاخه: {str(e)}"

    def list_files(self, path=""):
        """لیست فایل‌ها و پوشه‌ها در مخزن فعلی"""
        logger.info(f"درخواست لیست فایل‌ها و پوشه‌ها در مسیر {path}")
        if not self.current_repo:
            logger.error("هیچ مخزنی انتخاب نشده است")
            return "خطا: هیچ مخزنی انتخاب نشده است!", []
        try:
            contents = self.current_repo.get_contents(path)
            item_list = [(item.path, item.type) for item in contents]  # شامل فایل‌ها و پوشه‌ها
            if not item_list:
                logger.warning("هیچ فایل یا پوشه‌ای در مخزن یافت نشد")
                return "هیچ فایل یا پوشه‌ای در مخزن یافت نشد!", []
            numbered_list = "\n".join([f"{i+1}. {item[0]} ({'پوشه' if item[1] == 'dir' else 'فایل'})" for i, item in enumerate(item_list)])
            logger.info(f"لیست فایل‌ها و پوشه‌ها: {numbered_list}")
            return numbered_list, [item[0] for item in item_list]
        except Exception as e:
            logger.error(f"خطا در لیست فایل‌ها و پوشه‌ها: {str(e)}")
            return f"خطا در لیست فایل‌ها و پوشه‌ها: {str(e)}", []

    def create_pull_request(self, title, body, head_branch, base_branch="main"):
        """ایجاد درخواست Pull"""
        logger.info(f"تلاش برای ایجاد PR با عنوان {title}")
        if not self.current_repo:
            logger.error("هیچ مخزنی انتخاب نشده است")
            return "خطا: هیچ مخزنی انتخاب نشده است!"
        try:
            pr = self.current_repo.create_pull(title=title, body=body, head=head_branch, base=base_branch)
            logger.info(f"PR ایجاد شد: {pr.html_url}")
            return f"PR ایجاد شد: {pr.html_url}"
        except Exception as e:
            logger.error(f"خطا در ایجاد PR: {str(e)}")
            return f"خطا در ایجاد PR: {str(e)}"
