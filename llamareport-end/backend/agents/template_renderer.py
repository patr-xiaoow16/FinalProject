"""
Jinja2 模板渲染器
将结构化数据渲染为 Markdown 报告
"""

import logging
from pathlib import Path
from typing import Dict, Any
from jinja2 import Environment, FileSystemLoader, select_autoescape
from models.report_models import AnnualReportAnalysis

logger = logging.getLogger(__name__)


class TemplateRenderer:
    """模板渲染器"""
    
    def __init__(self, template_dir: str = "templates"):
        """
        初始化渲染器
        
        Args:
            template_dir: 模板目录路径
        """
        self.template_dir = Path(template_dir)
        
        # 确保模板目录存在
        if not self.template_dir.exists():
            raise FileNotFoundError(f"模板目录不存在: {self.template_dir}")
        
        # 创建 Jinja2 环境
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        logger.info(f"✅ TemplateRenderer 初始化成功,模板目录: {self.template_dir}")
    
    def render_report(
        self,
        report_data: Dict[str, Any],
        template_name: str = "annual_report_template.md.jinja2"
    ) -> str:
        """
        渲染年报分析报告
        
        Args:
            report_data: 报告数据(字典格式)
            template_name: 模板文件名
        
        Returns:
            渲染后的 Markdown 文本
        """
        try:
            # 加载模板
            template = self.env.get_template(template_name)
            
            # 渲染模板
            rendered = template.render(**report_data)
            
            logger.info(f"✅ 报告渲染成功,使用模板: {template_name}")
            return rendered
            
        except Exception as e:
            logger.error(f"❌ 报告渲染失败: {str(e)}")
            raise
    
    def render_from_pydantic(
        self,
        report: AnnualReportAnalysis,
        template_name: str = "annual_report_template.md.jinja2"
    ) -> str:
        """
        从 Pydantic 模型渲染报告
        
        Args:
            report: AnnualReportAnalysis 实例
            template_name: 模板文件名
        
        Returns:
            渲染后的 Markdown 文本
        """
        try:
            # 将 Pydantic 模型转换为字典
            report_dict = report.dict()
            
            # 渲染
            return self.render_report(report_dict, template_name)
            
        except Exception as e:
            logger.error(f"❌ 从 Pydantic 模型渲染失败: {str(e)}")
            raise
    
    def save_report(
        self,
        report_data: Dict[str, Any],
        output_path: str,
        template_name: str = "annual_report_template.md.jinja2"
    ) -> bool:
        """
        渲染并保存报告到文件
        
        Args:
            report_data: 报告数据
            output_path: 输出文件路径
            template_name: 模板文件名
        
        Returns:
            是否成功
        """
        try:
            # 渲染报告
            rendered = self.render_report(report_data, template_name)
            
            # 保存到文件
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(rendered)
            
            logger.info(f"✅ 报告已保存到: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 保存报告失败: {str(e)}")
            return False
    
    def render_section(
        self,
        section_data: Dict[str, Any],
        section_template: str
    ) -> str:
        """
        渲染单个章节
        
        Args:
            section_data: 章节数据
            section_template: 章节模板名称
        
        Returns:
            渲染后的文本
        """
        try:
            template = self.env.get_template(section_template)
            rendered = template.render(**section_data)
            
            logger.info(f"✅ 章节渲染成功: {section_template}")
            return rendered
            
        except Exception as e:
            logger.error(f"❌ 章节渲染失败: {str(e)}")
            raise
    
    def list_templates(self) -> list:
        """
        列出所有可用的模板
        
        Returns:
            模板文件名列表
        """
        try:
            templates = list(self.env.list_templates())
            logger.info(f"找到 {len(templates)} 个模板")
            return templates
            
        except Exception as e:
            logger.error(f"❌ 列出模板失败: {str(e)}")
            return []


# 便捷函数

def render_annual_report(
    report_data: Dict[str, Any],
    template_dir: str = "templates",
    template_name: str = "annual_report_template.md.jinja2"
) -> str:
    """
    便捷函数: 渲染年报分析报告
    
    Args:
        report_data: 报告数据
        template_dir: 模板目录
        template_name: 模板文件名
    
    Returns:
        渲染后的 Markdown 文本
    """
    renderer = TemplateRenderer(template_dir)
    return renderer.render_report(report_data, template_name)


def save_annual_report(
    report_data: Dict[str, Any],
    output_path: str,
    template_dir: str = "templates",
    template_name: str = "annual_report_template.md.jinja2"
) -> bool:
    """
    便捷函数: 渲染并保存年报分析报告
    
    Args:
        report_data: 报告数据
        output_path: 输出文件路径
        template_dir: 模板目录
        template_name: 模板文件名
    
    Returns:
        是否成功
    """
    renderer = TemplateRenderer(template_dir)
    return renderer.save_report(report_data, output_path, template_name)

