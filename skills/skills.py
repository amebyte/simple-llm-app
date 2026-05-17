import re
from pathlib import Path

class SkillsLoader:
    """
    技能加载器，负责从工作区中发现、加载和解析技能文件（SKILL.md）。
    
    技能目录约定：
        workspace/skills/<技能名称>/SKILL.md
    """
    
    def __init__(self, workspace: Path):
        """
        初始化技能加载器。
        
        Args:
            workspace: 工作区根目录路径，技能将位于 workspace/skills/ 下
        """
        self.workspace = workspace
        # 拼接出技能根目录的路径
        self.workspace_skills = workspace / "skills"
    
    def list_skills(self) -> list[dict[str, str]]:
        """
        发现工作区中所有可用的技能。
        
        遍历技能根目录下的每个子文件夹，检查是否存在 SKILL.md 文件。
        
        Returns:
            技能信息列表，每个元素为字典，包含：
                - name: 技能名称（文件夹名）
                - path: SKILL.md 文件的绝对路径
                - source: 技能来源（固定为 "workspace"）
        """
        skills = []
        
        # 仅当技能根目录存在时才进行遍历
        if self.workspace_skills.exists():
            for skill_dir in self.workspace_skills.iterdir():
                # 只处理文件夹，忽略文件
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    # 只收集存在 SKILL.md 的文件夹
                    if skill_file.exists():
                        skills.append({
                            "name": skill_dir.name,
                            "path": str(skill_file),
                            "source": "workspace"
                        })
        return skills
    
    def load_skill(self, name: str) -> str | None:
        """
        加载指定技能的原始内容（SKILL.md 全文）。
        
        Args:
            name: 技能名称（即技能文件夹名）
            
        Returns:
            技能文件的文本内容（UTF-8 编码），若文件不存在则返回 None
        """
        workspace_skill = self.workspace_skills / name / "SKILL.md"
        if workspace_skill.exists():
            return workspace_skill.read_text(encoding="utf-8")
        
        return None
    
    def build_skills_summary(self) -> str:
        """
        构建所有技能的摘要信息，以 XML 格式返回。
        
        摘要包含每个技能的名称、描述和文件位置，便于 LLM 或外部系统解析。
        
        Returns:
            XML 格式的技能摘要字符串，若无任何技能则返回空字符串。
        """
        all_skills = self.list_skills() 
        if not all_skills:
            return ""
        
        lines = ["<skills>"]
        for s in all_skills:
            name = s["name"]
            path = s["path"]
            # 获取该技能的元数据（描述等）
            meta = self.get_skill_metadata(name)
            # 假设元数据必然存在且包含 description 字段
            desc = meta["description"] 
            
            lines.append(f"  <skill>")
            lines.append(f"    <name>{name}</name>")
            lines.append(f"    <description>{desc}</description>")
            lines.append(f"    <location>{path}</location>")
            lines.append(f"  </skill>")
        lines.append("</skills>")
        
        return "\n".join(lines)
    
    def get_skill_metadata(self, name: str) -> dict | None:
        """
        从技能的 SKILL.md 中提取 YAML Front Matter 元数据。
        
        约定 Front Matter 格式：
            ---
            key1: value1
            key2: "value2"
            ---
        
        Args:
            name: 技能名称
            
        Returns:
            元数据字典，例如 {"description": "某个技能", "version": "1.0"}；
            若文件不存在或没有有效 Front Matter 则返回 None。
        """
        content = self.load_skill(name)
        if not content:
            return None
        
        # 检查文件是否以 "---\n" 开头，表示存在 Front Matter
        if content.startswith("---"):
            # 使用正则匹配最外层的一对 --- ... ---
            # re.DOTALL 使 . 也能匹配换行符，从而捕获多行元数据块
            match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            if match:
                # 提取元数据块中的每一行，进行简易的键值对解析
                metadata = {}
                for line in match.group(1).split("\n"):
                    # 只处理包含冒号的行（忽略空行或注释行）
                    if ":" in line:
                        key, value = line.split(":", 1)      # 仅按第一个冒号分割
                        # 去除键和值两端的空白字符，并去掉值两端的引号（单/双引号）
                        metadata[key.strip()] = value.strip().strip('"\'')
                return metadata
        
        return None