import re
from datetime import datetime
from jira import JIRAError


class PullRequest(object):
    """Объект для работы с ПР."""

    JIRA_ISSUE_URL_PATTERN = r'(?=(?P<tmp>http:\/\/www\.|https:\/\/www\.|http:\/\/|https:\/\/))(?P=tmp)' \
                             r'(?=(?P<tmp2>jira))(?P=tmp2)(?=(?P<tmp3>[\-\.]{1}))(?P=tmp3)(?=(?P<tmp4>\S*))(?P=tmp4)'
    JIRA_ISSUE_ID_PATTERN = r'\S*\/(\S*-[\d]*)'

    def __init__(self, client, jira_client, project, repository, **kwargs):
        """Создание объекта для работы с ПР.

        Args:
            client: Клиент для работы с Bitbucket.
            project: Наименование проекта в Bitbucket.
            repository: Наименование репозитория.
        Kwargs:
             id: the ID of the pull request within the repository.
             title: Заголовок ПРа.
             description: Описание ПРа.
             author: Автор ПРа.
             state: Состояние ПРа OPEN, DECLINED or MERGED.
             createdDate: Дата создания ПРа.
        """
        self.client = client,
        self.jira_client = jira_client
        self.project = project
        self.repository = repository
        self.id = kwargs.get('id')
        self.title = kwargs.get('title')
        self.description = kwargs.get('description')
        self.author = kwargs.get('author').get('user').get('displayName')
        self.state = kwargs.get('state')
        self.cre_date = datetime.fromtimestamp(kwargs.get('createdDate') / 1000)
        self.activities = []
        self.comments = []
        self.founded_url = None
        self.get_activities_and_comments()
        self.tests_count_in_pr = self.get_tests_count()
        self.component = self.get_jira_component_for_issues_in_pr()

    def get_activities_and_comments(self):
        """сбор комментов и severity"""
        self.activities = self.client[0].get_pull_requests_activities(project=self.project,
                                                                      repository=self.repository,
                                                                      pull_request_id=self.id)
        self.comments.extend([text['comment']['text'] for text in
                              [act for act in self.activities if act['action'] == 'COMMENTED']])

    def get_tests_count(self):
        """Определение кол-ва тестов по наличию ссылок на jira в description."""
        self.founded_url = re.findall(self.JIRA_ISSUE_URL_PATTERN, self.description) if self.description else None
        if self.founded_url is not None:
            self.founded_url = [''.join(f) for f in self.founded_url]
            return len(self.founded_url)

        return 0

    def get_jira_component_for_issues_in_pr(self):
        """Получение наименования компонента для тестов в ПРе (если заданы юзер и пароль Jira)."""
        component = None
        if self.founded_url is not None and self.jira_client is not None:
            for url in self.founded_url:
                try:
                    founded_id = re.findall(self.JIRA_ISSUE_ID_PATTERN, url)
                    if founded_id:
                        issue = self.jira_client.issue(id=founded_id[0])
                        component = getattr(issue.fields, 'components', None)
                        if component:
                            component = ','.join([c.name for c in component])
                            break
                except JIRAError:
                    continue
        return component if component is not None else 'NoComponent'


class PullRequestsByAuthor(object):
    """Объект для работы с информацией о ПРе для отдельного Автора."""

    COMMON_PATTERN = r'^\[(..)]'
    HIGH_PATTERN = r'^h.'
    MEDIUM_PATTERN = r'^m.'
    LOW_PATTERN = r'^l.'

    def __init__(self, author, repository, component, tests_count):
        """Создание объекта для работы с информацией о ПРе для отдельного Автора.

        Args:
            author: Автор ПРа.
            repository: Наименование репозитория.
            tests_count: Кол-во тестов
        """
        self.author = author
        self.repository = repository
        self.component = component
        self.tests_count = tests_count
        self.pr_count = 0
        self.faults = 0
        self.high = 0
        self.medium = 0
        self.low = 0
        self.hr = self.hs = self.hl = self.hx = self.hc = self.mr = self.ms = self.ml = 0
        self.mx = self.mc = self.lr = self.ls = self.ll = self.lx = self.lc = self.no_category = 0
        self.founded_severities = []
        self.comments = []

    def count_faults(self):
        """Подсчет ошибок. Сбор инфы по категориям ошибки."""
        for comment in self.comments:
            string = re.findall(self.COMMON_PATTERN, comment)
            if not string:
                self.no_category += 1
            else:
                self.founded_severities.extend(string)

        self.get_faults_severity()

    def get_faults_severity(self):
        """Сбор инфы по категориям ошибки."""
        for string in self.founded_severities:
            for pattern in [self.HIGH_PATTERN, self.MEDIUM_PATTERN, self.LOW_PATTERN]:
                severity = re.findall(pattern, string)
                if severity and pattern == self.HIGH_PATTERN:
                    self.high += 1
                if severity and pattern == self.MEDIUM_PATTERN:
                    self.medium += 1
                if severity and pattern == self.LOW_PATTERN:
                    self.low += 1
                for item in severity:
                    setattr(self, item, getattr(self, item) + 1)
