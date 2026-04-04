import os
import yaml
import logging

logger = logging.getLogger(__name__)

class WorkspaceManager:
    """
    工作区管理器：根据配置动态生成和维护部门与个人的工作区 (包含 inbox 和 outbox)
    遵循原则：开发所有模块都要尽可能考虑解耦合和接口化，代码要易维护
    """

    def __init__(self, config_path: str, workspace_root: str):
        self.config_path = config_path
        self.workspace_root = workspace_root

    def _ensure_dir(self, path: str):
        """确保目录存在"""
        if not os.path.exists(path):
            os.makedirs(path)
            logger.info(f"创建目录: {path}")

    def _create_inbox_outbox(self, base_path: str):
        """在指定基础路径下创建 inbox 和 outbox 目录"""
        self._ensure_dir(os.path.join(base_path, "inbox"))
        self._ensure_dir(os.path.join(base_path, "outbox"))

    def sync_workspaces(self):
        """
        读取 YAML 配置文件，并同步生成/更新相应的部门和个人工作区结构。
        所有信息的收发流转均在此结构内的 Markdown 文件中实现。
        """
        if not os.path.exists(self.config_path):
            logger.warning(f"组织架构配置文件不存在: {self.config_path}")
            return

        with open(self.config_path, 'r', encoding='utf-8') as f:
            try:
                org_data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                logger.error(f"解析组织架构配置文件失败: {e}")
                return

        projects = org_data.get('projects', [])
        
        # 定义基础工作区路径
        dept_workspace_root = os.path.join(self.workspace_root, "projects")
        emp_workspace_root = os.path.join(self.workspace_root, "employees")

        # 遍历项目并创建对应工作区
        for dept in projects:
            dept_name = dept.get('name')
            if not dept_name:
                continue
                
            # 为项目创建 inbox/outbox
            dept_path = os.path.join(dept_workspace_root, dept_name)
            self._create_inbox_outbox(dept_path)
            
            # 遍历项目下的员工并创建对应工作区
            members = dept.get('members', [])
            for member in members:
                member_name = member.get('emp_id')
                if not member_name:
                    continue
                emp_path = os.path.join(emp_workspace_root, member_name)
                self._create_inbox_outbox(emp_path)
                
        logger.info("工作区目录结构同步完成。")

if __name__ == "__main__":
    # 简单测试逻辑
    logging.basicConfig(level=logging.INFO)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(current_dir, '..', '..', 'config', 'org_chart.yaml')
    workspace_dir = os.path.join(current_dir, '..', '..', 'data', 'workspace')
    
    manager = WorkspaceManager(config_file, workspace_dir)
    manager.sync_workspaces()
