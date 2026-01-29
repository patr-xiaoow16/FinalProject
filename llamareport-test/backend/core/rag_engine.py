"""
简化的RAG引擎
专注于文档索引构建和智能问答
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
from llama_index.core import Document, VectorStoreIndex, StorageContext, Settings
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.storage.index_store import SimpleIndexStore
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.llms.deepseek import DeepSeek
from llama_index.embeddings.openai import OpenAIEmbedding
import chromadb

# 导入Hybrid Retriever
from .hybrid_retriever import HybridRetriever

logger = logging.getLogger(__name__)

class RAGEngine:
    """简化的RAG引擎"""
    
    def __init__(self, storage_dir: str = "./storage", collection_name: str = "documents"):
        self.storage_dir = Path(storage_dir)
        self.collection_name = collection_name
        self.index = None
        self.query_engine = None
        self.chroma_client = None
        self.chroma_collection = None
        
        # 确保存储目录存在
        self.storage_dir.mkdir(exist_ok=True)
        
        # 设置LlamaIndex
        self.llama_index_ready = self._setup_llama_index()

        # 初始化ChromaDB
        if self.llama_index_ready:
            self._setup_chroma()
        else:
            logger.warning("⚠️ 跳过ChromaDB初始化 - LlamaIndex未就绪")
        
        # 初始化Hybrid Retriever
        self.hybrid_retriever = HybridRetriever(storage_dir=str(self.storage_dir))
        self.use_hybrid_retriever = True  # 默认启用混合检索
    
    def _setup_llama_index(self):
        """设置LlamaIndex配置"""
        try:
            # 获取 API Keys
            openai_api_key = os.getenv("OPENAI_API_KEY")
            deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")

            if not openai_api_key:
                logger.warning("⚠️ OPENAI_API_KEY未设置，Embedding功能将受限")
                return False

            if not deepseek_api_key:
                logger.warning("⚠️ DEEPSEEK_API_KEY未设置，对话功能将受限")
                return False

            # 设置LLM - 使用 DeepSeek 专用集成
            deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

            Settings.llm = DeepSeek(
                model=deepseek_model,
                api_key=deepseek_api_key,
                temperature=0.1
            )

            logger.info(f"✅ DeepSeek LLM配置成功 - 模型: {deepseek_model}")

            # 设置嵌入模型 - 继续使用 OpenAI
            Settings.embed_model = OpenAIEmbedding(
                model="text-embedding-3-small",
                api_key=openai_api_key
            )

            logger.info("✅ OpenAI Embedding配置成功")
            logger.info("✅ LlamaIndex配置成功 (DeepSeek LLM + OpenAI Embedding)")
            return True

        except Exception as e:
            logger.error(f"❌ LlamaIndex配置失败: {str(e)}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return False
    
    def _setup_chroma(self):
        """设置ChromaDB"""
        try:
            # 使用持久化客户端
            chroma_persist_dir = self.storage_dir / "chroma"
            chroma_persist_dir.mkdir(exist_ok=True)
            
            self.chroma_client = chromadb.PersistentClient(path=str(chroma_persist_dir))
            
            # 尝试获取现有集合，如果不存在则创建
            try:
                self.chroma_collection = self.chroma_client.get_collection(self.collection_name)
                logger.info(f"✅ 加载现有ChromaDB集合: {self.collection_name}")
            except:
                self.chroma_collection = self.chroma_client.create_collection(self.collection_name)
                logger.info(f"✅ 创建新的ChromaDB集合: {self.collection_name}")
            
        except Exception as e:
            logger.error(f"❌ ChromaDB设置失败: {str(e)}")
            raise

    def load_existing_index(self) -> bool:
        """从现有的ChromaDB集合加载索引"""
        try:
            logger.info(f"🔄 开始加载索引...")
            logger.info(f"   存储目录: {self.storage_dir.absolute()}")
            logger.info(f"   ChromaDB路径: {(self.storage_dir / 'chroma').absolute()}")
            
            if not self.llama_index_ready:
                logger.error("❌ LlamaIndex未就绪，无法加载索引")
                logger.error("   请检查 OPENAI_API_KEY 和 DEEPSEEK_API_KEY 环境变量")
                return False

            if not self.chroma_collection:
                logger.error("❌ ChromaDB集合未初始化")
                logger.error(f"   集合名称: {self.collection_name}")
                return False

            # 检查集合是否有数据
            collection_count = self.chroma_collection.count()
            logger.info(f"📊 ChromaDB集合 '{self.collection_name}' 包含 {collection_count} 个向量")
            
            if collection_count == 0:
                logger.warning("⚠️ ChromaDB集合为空，无法加载索引")
                logger.warning(f"   存储目录: {self.storage_dir.absolute()}")
                logger.warning(f"   ChromaDB路径: {(self.storage_dir / 'chroma').absolute()}")
                logger.warning("   请先处理文档并构建索引")
                return False

            # 创建向量存储
            from llama_index.vector_stores.chroma import ChromaVectorStore
            from llama_index.core import StorageContext

            vector_store = ChromaVectorStore(chroma_collection=self.chroma_collection)

            # 从向量存储加载索引
            self.index = VectorStoreIndex.from_vector_store(vector_store)

            # 创建查询引擎 - 优化配置
            from llama_index.core.prompts import PromptTemplate

            # 自定义系统提示词，强调使用表格数据
            qa_prompt_tmpl = (
                "你是一个专业的财务分析助手。下面是从文档中检索到的相关内容：\n\n"
                "{context_str}\n\n"
                "请仔细阅读上述内容，特别注意其中的表格数据。如果内容中包含Markdown格式的表格，"
                "请务必分析表格中的具体数值。\n\n"
                "用户问题：{query_str}\n\n"
                "回答要求：\n"
                "1. 必须基于检索到的具体数据回答，特别是表格中的数值\n"
                "2. 如果找到相关数据，请引用具体数字和来源\n"
                "3. 如果数据不足，明确说明缺少哪些信息\n"
                "4. 对于趋势分析，需要对比不同时期的数据\n\n"
                "请提供详细、准确的回答："
            )
            qa_prompt = PromptTemplate(qa_prompt_tmpl)

            self.query_engine = self.index.as_query_engine(
                similarity_top_k=20,  # 增加检索数量（从10增加到20，提高检索精度）
                response_mode="compact",  # 使用compact模式保留更多细节
                text_qa_template=qa_prompt,
                verbose=True
            )

            logger.info(f"✅ 成功从ChromaDB加载索引，包含 {collection_count} 个向量")
            
            # 同时尝试加载Hybrid Retriever索引
            if self.use_hybrid_retriever:
                logger.info("🔄 尝试加载Hybrid Retriever索引...")
                hybrid_loaded = self.hybrid_retriever.load_existing_index()
                if hybrid_loaded:
                    logger.info("✅ Hybrid Retriever索引加载成功")
                else:
                    logger.warning("⚠️ Hybrid Retriever索引未加载（可能需要重新构建）")
            
            return True

        except Exception as e:
            logger.error(f"❌ 加载索引失败: {str(e)}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return False
    
    def build_index(self, processed_documents: Dict[str, Any], extracted_tables: Dict[str, List[Dict]] = None, incremental: bool = True) -> bool:
        """
        构建向量索引（支持增量更新）

        Args:
            processed_documents: 处理过的文档
            extracted_tables: 提取的表格（可选）
            incremental: 是否使用增量更新模式（默认True，只添加新文件，保留已有索引）

        Returns:
            是否成功构建索引
        """
        if not self.llama_index_ready:
            logger.error("❌ LlamaIndex未就绪，无法构建索引")
            return False

        try:
            # 🔍 打印索引构建开始信息
            print("\n" + "=" * 80)
            print("🚀 开始构建RAG索引" + ("（增量模式）" if incremental else "（重建模式）"))
            print("=" * 80)
            
            # 检查已索引的文件（增量模式下）
            indexed_files = set()
            if incremental and self.chroma_collection:
                try:
                    # 获取所有已索引的文档，提取source_file元数据
                    existing_data = self.chroma_collection.get()
                    if existing_data and 'metadatas' in existing_data:
                        for metadata in existing_data.get('metadatas', []):
                            if metadata and 'source_file' in metadata:
                                indexed_files.add(metadata['source_file'])
                    if indexed_files:
                        logger.info(f"📋 已索引的文件: {', '.join(indexed_files)}")
                except Exception as e:
                    logger.warning(f"⚠️ 检查已索引文件失败: {str(e)}，将重新构建索引")
                    indexed_files = set()
            
            # 确定需要索引的文件（增量模式下，只索引新文件）
            files_to_index = set(processed_documents.keys())
            if incremental:
                new_files = files_to_index - indexed_files
                if new_files:
                    logger.info(f"📝 新文件需要索引: {', '.join(new_files)}")
                else:
                    logger.info("✅ 所有文件已索引，跳过索引构建")
                    # 如果所有文件都已索引，尝试加载现有索引
                    if not self.index:
                        return self.load_existing_index()
                    return True
                # 只处理新文件
                processed_documents = {k: v for k, v in processed_documents.items() if k in new_files}
                if extracted_tables:
                    extracted_tables = {k: v for k, v in extracted_tables.items() if k in new_files}
            
            all_documents = []
            
            # 处理文本文档
            print("📄 处理文本文档:")
            text_doc_count = 0
            financial_statement_count = 0
            for doc_name, doc_data in processed_documents.items():
                if 'documents' in doc_data:
                    print(f"  - {doc_name}: {len(doc_data['documents'])}个文档片段")
                    for doc in doc_data['documents']:
                        # 添加元数据
                        doc.metadata.update({
                            'source_file': doc_name,
                            'document_type': 'text_content'
                        })
                        
                        # 如果是财务报表，添加优先级标记
                        if doc.metadata.get('is_financial_statement', False):
                            doc.metadata['priority'] = 'high'
                            doc.metadata['financial_statement_type'] = doc.metadata.get('financial_statement_type', 'unknown')
                            financial_statement_count += 1
                            # 在文本前添加标记，提高检索权重
                            doc.text = f"[财务报表-{doc.metadata.get('financial_statement_type', 'unknown')}] {doc.text}"
                        
                        all_documents.append(doc)
                        text_doc_count += 1
            
            if financial_statement_count > 0:
                print(f"  📊 财务报表数量: {financial_statement_count}")
            
            print(f"  📊 文本文档总数: {text_doc_count}")
            
            # 处理表格数据
            table_doc_count = 0
            if extracted_tables:
                print("\n📊 处理表格数据:")
                for doc_name, tables in extracted_tables.items():
                    print(f"  - {doc_name}: {len(tables)}个表格")
                    for table in tables:
                        # 将表格转换为文本
                        table_text = self._table_to_text(table)
                        
                        table_doc = Document(
                            text=table_text,
                            metadata={
                                'source_file': doc_name,
                                'document_type': 'table_data',
                                'table_id': table['table_id'],
                                'page_number': table['page_number'],
                                'is_financial': table.get('is_financial', False),
                                'importance_score': table.get('importance_score', 0.0)
                            }
                        )
                        all_documents.append(table_doc)
                        table_doc_count += 1
                        
                        # 打印表格转换示例（前2个）
                        if table_doc_count <= 2:
                            print(f"    📋 表格{table_doc_count}: {table['table_id']}")
                            print(f"       - 财务表格: {'是' if table.get('is_financial', False) else '否'}")
                            print(f"       - 重要性: {table.get('importance_score', 0.0):.2f}")
                            print(f"       - 文本长度: {len(table_text)}字符")
                
                print(f"  📊 表格文档总数: {table_doc_count}")
            else:
                print("\n📊 表格数据: 无")
            
            if not all_documents:
                logger.warning("没有新文档需要索引")
                # 如果没有新文档，尝试加载现有索引
                if not self.index:
                    return self.load_existing_index()
                return True
            
            print(f"\n📈 索引统计:")
            print(f"  - 新文档数: {len(all_documents)}")
            print(f"  - 文本文档: {text_doc_count}")
            print(f"  - 表格文档: {table_doc_count}")
            
            # 创建向量存储
            print(f"\n🔧 创建向量存储...")
            vector_store = ChromaVectorStore(chroma_collection=self.chroma_collection)
            
            # 创建存储上下文
            print(f"🔧 创建存储上下文...")
            storage_context = StorageContext.from_defaults(
                docstore=SimpleDocumentStore(),
                index_store=SimpleIndexStore(),
                vector_store=vector_store
            )
            
            # 构建索引（增量模式下，如果已有索引则添加文档，否则新建）
            print(f"🔧 {'添加文档到索引' if incremental and self.index else '构建向量索引'}...")
            if incremental and self.index:
                # 增量模式：添加新文档到现有索引
                for doc in all_documents:
                    self.index.insert(doc)
            else:
                # 新建索引
                self.index = VectorStoreIndex.from_documents(
                    all_documents,
                    storage_context=storage_context
                )
            
            # 创建查询引擎 - 优化配置
            print(f"🔧 创建查询引擎...")
            from llama_index.core.prompts import PromptTemplate

            # 自定义系统提示词，强调使用表格数据
            qa_prompt_tmpl = (
                "你是一个专业的财务分析助手。下面是从文档中检索到的相关内容：\n\n"
                "{context_str}\n\n"
                "请仔细阅读上述内容，特别注意其中的表格数据。如果内容中包含Markdown格式的表格，"
                "请务必分析表格中的具体数值。\n\n"
                "用户问题：{query_str}\n\n"
                "回答要求：\n"
                "1. 必须基于检索到的具体数据回答，特别是表格中的数值\n"
                "2. 如果找到相关数据，请引用具体数字和来源\n"
                "3. 如果数据不足，明确说明缺少哪些信息\n"
                "4. 对于趋势分析，需要对比不同时期的数据\n\n"
                "请提供详细、准确的回答："
            )
            qa_prompt = PromptTemplate(qa_prompt_tmpl)

            self.query_engine = self.index.as_query_engine(
                similarity_top_k=20,  # 增加检索数量（从10增加到20，提高检索精度）
                response_mode="compact",  # 使用compact模式保留更多细节
                text_qa_template=qa_prompt,
                verbose=True
            )
            
            # 🔍 打印索引构建完成信息
            print(f"\n✅ 索引构建完成!")
            print(f"  - 文档总数: {len(all_documents)}")
            print(f"  - 向量存储: ChromaDB")
            print(f"  - 集合名称: {self.collection_name}")
            print(f"  - 检索数量: 10")
            print(f"  - 响应模式: compact")
            print("=" * 80)
            
            # 构建Hybrid Retriever索引
            if self.use_hybrid_retriever:
                print("🚀 构建Hybrid Retriever索引...")
                hybrid_success = self.hybrid_retriever.build_hybrid_index(
                    processed_documents, extracted_tables
                )
                if hybrid_success:
                    print("✅ Hybrid Retriever索引构建成功")
                    hybrid_stats = self.hybrid_retriever.get_stats()
                    print(f"  - 文本索引: {hybrid_stats['text_collection_count']}个文档")
                    print(f"  - 表格索引: {hybrid_stats['table_collection_count']}个文档")
                    print(f"  - 财务指标: {hybrid_stats['financial_metrics_count']}个")
                else:
                    print("❌ Hybrid Retriever索引构建失败")
            
            logger.info(f"✅ 成功构建索引，包含 {len(all_documents)} 个文档")
            return True
            
        except Exception as e:
            logger.error(f"❌ 构建索引失败: {str(e)}")
            return False
    
    def _table_to_text(self, table: Dict[str, Any]) -> str:
        """将表格转换为文本表示 - 优化版本，生成更易于LLM理解的格式"""
        try:
            text_parts = []

            # 添加表格基本信息和上下文
            text_parts.append("=" * 80)
            text_parts.append(f"📊 表格数据 - {table['table_id']}")
            text_parts.append(f"📄 来源页码: 第{table['page_number']}页")

            # 标注表格类型
            if table.get('is_financial'):
                text_parts.append("💰 类型: 财务数据表格")

            if table.get('summary'):
                text_parts.append(f"📝 表格摘要: {table['summary']}")

            text_parts.append("=" * 80)

            # 添加表格数据 - 使用Markdown表格格式
            if 'table_data' in table:
                table_data = table['table_data']
                columns = table_data['columns']
                data_rows = table_data['data']

                # 提取表格中的关键财务指标（从列名中）
                financial_indicators = []
                common_indicators = ['营业收入', '营收', '收入', '净利润', '利润', '资产', '负债', '资产总额', 
                                   'ROE', 'ROA', '毛利率', '净利率', '总资产', '净资产', '股东权益']
                for col in columns:
                    col_str = str(col)
                    for indicator in common_indicators:
                        if indicator in col_str:
                            financial_indicators.append(indicator)
                            break
                
                # 如果识别到财务指标，在开头标注
                if financial_indicators:
                    text_parts.append(f"\n💰 **包含的财务指标**: {', '.join(set(financial_indicators))}")

                # 生成Markdown表格
                text_parts.append("\n**表格内容（Markdown格式）：**\n")

                # 表头
                header = "| " + " | ".join([str(col) for col in columns]) + " |"
                text_parts.append(header)

                # 分隔线
                separator = "|" + "|".join(["---" for _ in columns]) + "|"
                text_parts.append(separator)

                # 数据行 - 显示所有行或最多30行
                max_rows = min(len(data_rows), 30)
                for i, row in enumerate(data_rows[:max_rows]):
                    row_str = "| " + " | ".join([str(cell) if cell else "" for cell in row]) + " |"
                    text_parts.append(row_str)

                if len(data_rows) > max_rows:
                    text_parts.append(f"\n... (表格共有 {len(data_rows)} 行数据，以上显示前 {max_rows} 行)")
                else:
                    text_parts.append(f"\n(表格共有 {len(data_rows)} 行数据)")

                # 添加数据统计信息
                text_parts.append(f"\n**表格维度**: {len(data_rows)} 行 × {len(columns)} 列")

                # 对于财务表格，添加特别提示
                if table.get('is_financial'):
                    text_parts.append("\n⚠️ **重要提示**: 这是财务数据表格，包含具体的数值信息。请仔细分析表格中的数据来回答问题。")

            text_parts.append("=" * 80 + "\n")

            result_text = "\n".join(text_parts)
            
            # 🔍 打印表格转换信息（仅前2个表格）
            if hasattr(self, '_table_count'):
                self._table_count += 1
            else:
                self._table_count = 1
                
            if self._table_count <= 2:
                print(f"    🔄 表格转换: {table['table_id']}")
                print(f"       - 原始数据: {len(table.get('table_data', {}).get('data', []))}行")
                print(f"       - 转换后长度: {len(result_text)}字符")
                print(f"       - 包含Markdown: {'是' if '|' in result_text else '否'}")

            return result_text

        except Exception as e:
            logger.error(f"表格转文本失败: {str(e)}")
            return f"表格 {table.get('table_id', 'unknown')} (转换失败: {str(e)})"
    
    def query(self, question: str, context_filter: Optional[Dict] = None) -> Dict[str, Any]:
        """
        查询RAG系统

        Args:
            question: 查询问题
            context_filter: 上下文过滤器（可选）

        Returns:
            查询结果
        """
        try:
            # 🔍 打印查询开始信息
            print("\n" + "=" * 80)
            print("🔍 开始RAG查询")
            print("=" * 80)
            print(f"📝 原始问题: {question}")
            
            if not self.llama_index_ready:
                print("❌ RAG系统未就绪")
                return {
                    'answer': "RAG系统未就绪，请检查OPENAI_API_KEY配置。",
                    'sources': [],
                    'error': True
                }

            if not self.query_engine:
                print("🔄 尝试加载现有索引...")
                logger.info(f"查询引擎未初始化，尝试加载现有索引...")
                logger.info(f"存储目录: {self.storage_dir.absolute()}")
                
                # 尝试从现有的ChromaDB集合加载索引
                if not self.load_existing_index():
                    print("❌ 无法加载现有索引")
                    # 检查具体原因
                    error_details = []
                    if not self.llama_index_ready:
                        error_details.append("LlamaIndex未就绪（请检查API密钥）")
                    elif not self.chroma_collection:
                        error_details.append("ChromaDB集合未初始化")
                    elif self.chroma_collection and self.chroma_collection.count() == 0:
                        error_details.append(f"ChromaDB集合 '{self.collection_name}' 为空")
                    else:
                        error_details.append("索引加载失败（请查看日志）")
                    
                    error_msg = "RAG系统未初始化: " + "；".join(error_details) + "。请先处理文档并构建索引。"
                    logger.error(f"❌ {error_msg}")
                    return {
                        'answer': error_msg,
                        'sources': [],
                        'error': True
                    }
                print("✅ 成功加载现有索引")
                logger.info("✅ 索引加载成功，可以开始查询")
            
            # 增强查询
            print("🔧 增强查询...")
            enhanced_query = self._enhance_query(question, context_filter)
            print(f"📝 增强后查询: {enhanced_query[:200]}...")
            
            # 执行查询
            if self.use_hybrid_retriever and self.hybrid_retriever.text_index and self.hybrid_retriever.table_index:
                print("🔍 使用Hybrid Retriever执行混合检索...")
                if context_filter:
                    print(f"🔍 应用上下文过滤器: {context_filter}")
                # 使用Hybrid Retriever进行检索，传递context_filter
                hybrid_results = self.hybrid_retriever.retrieve(question, top_k=10, context_filter=context_filter)
                
                if hybrid_results:
                    print(f"📊 Hybrid Retriever检索结果:")
                    print(f"  - 检索到文档: {len(hybrid_results)}个")
                    print(f"  - 平均综合评分: {sum(r['comprehensive_score'] for r in hybrid_results)/len(hybrid_results):.3f}")
                    print(f"  - 策略: {hybrid_results[0]['strategy']}")
                    
                    # 显示检索到的文档来源（用于调试）
                    if hybrid_results:
                        print(f"  - 文档来源:")
                        for i, result in enumerate(hybrid_results[:3], 1):
                            metadata = result['document'].metadata
                            filename = metadata.get('filename') or metadata.get('source_file', 'unknown')
                            print(f"      {i}. {filename}")
                    
                    # 构建上下文（使用过滤后的结果）
                    context = "\n\n".join([r['document'].text for r in hybrid_results])
                    
                    # 使用过滤后的上下文直接生成回答，而不是重新查询
                    # 这样可以确保只使用过滤后的文档
                    from llama_index.core import Settings
                    from llama_index.core.llms import ChatMessage
                    
                    # 构建包含过滤后上下文的提示词
                    context_prompt = f"""{enhanced_query}

【检索到的文档内容】
{context}

请基于以上检索到的文档内容回答问题。如果文档内容中没有相关信息，请明确说明。"""
                    
                    # 使用LLM直接生成回答（同步方式）
                    llm = Settings.llm
                    messages = [
                        ChatMessage(role="system", content="你是一个专业的财务分析助手。请基于提供的文档内容准确回答问题，不要编造信息。"),
                        ChatMessage(role="user", content=context_prompt)
                    ]
                    # 使用同步方法
                    try:
                        response_obj = llm.chat(messages)
                        # 提取响应文本
                        if hasattr(response_obj, 'message'):
                            response = str(response_obj.message.content)
                        elif hasattr(response_obj, 'content'):
                            response = str(response_obj.content)
                        else:
                            response = str(response_obj)
                    except Exception as e:
                        logger.error(f"LLM生成回答失败: {str(e)}")
                        # 如果LLM调用失败，回退到query_engine（但使用过滤后的上下文）
                        response = f"基于检索到的文档内容：\n\n{context[:1000]}...\n\n（注意：这是从过滤后的文档中提取的内容）"
                    
                    # 提取来源信息
                    sources = []
                    for result in hybrid_results:
                        sources.append({
                            'text': result['document'].text[:200] + "..." if len(result['document'].text) > 200 else result['document'].text,
                            'metadata': result['document'].metadata,
                            'score': result['comprehensive_score'],
                            'sim_score': result['sim_score'],
                            'metric_score': result['metric_score'],
                            'year_score': result['year_score']
                        })
                else:
                    print("⚠️ Hybrid Retriever未找到结果，回退到传统检索")
                    response = self.query_engine.query(enhanced_query)
                    sources = self._extract_sources(response)
                    # 对传统检索结果也应用过滤
                    if context_filter:
                        sources = self._filter_sources(sources, context_filter)
            else:
                print("🔍 执行传统向量检索和LLM生成...")
                if context_filter:
                    print(f"🔍 应用上下文过滤器: {context_filter}")
                # 检查Hybrid Retriever索引状态
                if self.use_hybrid_retriever:
                    text_ready = self.hybrid_retriever.text_index is not None
                    table_ready = self.hybrid_retriever.table_index is not None
                    print(f"   Hybrid Retriever状态: 文本索引={'✅' if text_ready else '❌'}, 表格索引={'✅' if table_ready else '❌'}")
                    if not text_ready or not table_ready:
                        print("   ⚠️ Hybrid Retriever索引未完全加载，使用传统检索")
                        print("   💡 提示: 如果检索结果不准确，请重新处理文档以构建Hybrid Retriever索引")
                
                # 如果有context_filter，使用retriever手动过滤
                if context_filter and self.index:
                    print("🔍 使用带过滤的检索器...")
                    retriever = self.index.as_retriever(similarity_top_k=30)  # 扩大检索范围
                    nodes = retriever.retrieve(question)
                    # 应用过滤
                    filtered_nodes = self._filter_nodes(nodes, context_filter)
                    if filtered_nodes:
                        # 使用过滤后的节点构建上下文
                        context_text = "\n\n".join([node.text for node in filtered_nodes[:10]])
                        # 使用query_engine但限制在过滤后的节点
                        response = self.query_engine.query(enhanced_query)
                        # 提取来源时只使用过滤后的节点
                        sources = []
                        for node in filtered_nodes[:10]:
                            sources.append({
                                'text': node.text[:200] + "..." if len(node.text) > 200 else node.text,
                                'metadata': node.metadata,
                                'score': getattr(node, 'score', 0.0)
                            })
                    else:
                        print("⚠️ 过滤后没有匹配的文档")
                        response = self.query_engine.query(enhanced_query)
                        sources = self._extract_sources(response)
                else:
                    response = self.query_engine.query(enhanced_query)
                    # 提取来源信息
                    print("📚 提取来源信息...")
                    sources = self._extract_sources(response)
                    # 对传统检索结果也应用过滤
                    if context_filter:
                        sources = self._filter_sources(sources, context_filter)
                
                # 打印检索到的来源摘要（帮助诊断）
                if sources:
                    print(f"   📋 检索到的来源摘要:")
                    for i, source in enumerate(sources[:3], 1):
                        source_type = source.get('metadata', {}).get('document_type', 'unknown')
                        source_text = source.get('text', '')
                        source_preview = source_text[:150].replace('\n', ' ')
                        
                        # 检查是否包含查询关键词
                        question_lower = question.lower()
                        contains_keyword = any(keyword in source_text.lower() for keyword in question_lower.split())
                        
                        relevance_marker = "✅" if contains_keyword else "⚠️"
                        print(f"      {i}. [{source_type}] {relevance_marker} {source_preview}...")
                        
                        # 如果是表格，显示表格ID
                        if source_type == 'table_data':
                            table_id = source.get('metadata', {}).get('table_id', 'unknown')
                            page_num = source.get('metadata', {}).get('page_number', 'unknown')
                            print(f"         表格ID: {table_id}, 页码: {page_num}")
            
            result = {
                'answer': str(response),
                'sources': sources,
                'error': False,
                'original_question': question,
                'enhanced_query': enhanced_query
            }
            
            # 🔍 打印查询结果信息
            print(f"\n✅ 查询完成!")
            print(f"  - 检索到来源: {len(sources)}个")
            print(f"  - 回答长度: {len(str(response))}字符")
            print(f"  - 来源类型: {[s.get('metadata', {}).get('document_type', 'unknown') for s in sources[:3]]}")
            print("=" * 80)
            
            logger.info(f"✅ 查询成功: {question[:50]}...")
            return result
            
        except Exception as e:
            print(f"❌ 查询失败: {str(e)}")
            logger.error(f"❌ 查询失败: {str(e)}")
            return {
                'answer': f"查询失败: {str(e)}",
                'sources': [],
                'error': True
            }
    
    def _enhance_query(self, question: str, context_filter: Optional[Dict] = None) -> str:
        """增强查询 - 优化版本，确保LLM使用检索到的数据"""
        enhanced_parts = []

        # 添加明确的指令
        enhanced_parts.append("【重要指令】请仔细阅读下面检索到的文档内容，特别是表格数据，并基于这些具体数据来回答问题。")
        enhanced_parts.append("如果检索到的内容中包含表格，请务必分析表格中的数值数据。")
        enhanced_parts.append("")

        # 提取关键词并强调（特别是财务指标）
        financial_keywords = ['营业收入', '净利润', '资产', '负债', '资产总额', 'ROE', 'ROA', '毛利率', '净利率']
        question_keywords = []
        for keyword in financial_keywords:
            if keyword in question:
                question_keywords.append(keyword)
        
        if question_keywords:
            enhanced_parts.append(f"【关键指标】本次查询重点关注以下财务指标: {', '.join(question_keywords)}")
            enhanced_parts.append("请优先检索和回答与这些指标相关的数据。")
            enhanced_parts.append("")

        # 添加原始问题
        enhanced_parts.append(f"【用户问题】{question}")
        enhanced_parts.append("")

        # 添加上下文过滤
        if context_filter:
            enhanced_parts.append("【查询条件】")
            if 'company' in context_filter:
                enhanced_parts.append(f"- 公司: {context_filter['company']}")

            if 'year' in context_filter:
                enhanced_parts.append(f"- 年份: {context_filter['year']} 年")

            if 'document_type' in context_filter:
                enhanced_parts.append(f"- 文档类型: {context_filter['document_type']}")

            enhanced_parts.append("")

        # 添加回答要求
        enhanced_parts.append("【回答要求】")
        enhanced_parts.append("1. 必须使用检索到的具体数据（特别是表格中的数值）")
        enhanced_parts.append("2. 如果数据不足，明确说明缺少哪些信息")
        enhanced_parts.append("3. 提供数据来源（页码、表格ID等）")
        enhanced_parts.append("4. 对于趋势分析，需要对比不同时期的数据")

        return "\n".join(enhanced_parts)
    
    def _extract_sources(self, response) -> List[Dict[str, Any]]:
        """提取来源信息"""
        sources = []
        
        try:
            if hasattr(response, 'source_nodes'):
                for node in response.source_nodes:
                    source_info = {
                        'text': node.text[:200] + "..." if len(node.text) > 200 else node.text,
                        'metadata': node.metadata,
                        'score': getattr(node, 'score', 0.0)
                    }
                    sources.append(source_info)
        except Exception as e:
            logger.warning(f"提取来源信息失败: {str(e)}")
        
        return sources
    
    def get_similar_content(self, query: str, top_k: int = 5) -> List[Dict]:
        """获取相似内容"""
        try:
            if not self.index:
                return []
            
            retriever = self.index.as_retriever(similarity_top_k=top_k)
            nodes = retriever.retrieve(query)
            
            similar_content = []
            for node in nodes:
                content = {
                    'text': node.text,
                    'score': getattr(node, 'score', 0.0),
                    'metadata': node.metadata
                }
                similar_content.append(content)
            
            return similar_content
            
        except Exception as e:
            logger.error(f"获取相似内容失败: {str(e)}")
            return []
    
    def _filter_nodes(self, nodes: List, context_filter: Dict[str, Any]) -> List:
        """过滤节点列表"""
        filtered = []
        for node in nodes:
            metadata = node.metadata
            match = True
            
            # 文件名过滤
            if 'filename' in context_filter:
                filename = context_filter['filename']
                doc_filename = metadata.get('filename') or metadata.get('source_file', '')
                if filename not in doc_filename and doc_filename not in filename:
                    match = False
            
            # 源文件过滤
            if match and 'source_file' in context_filter:
                source_file = context_filter['source_file']
                doc_source = metadata.get('source_file') or metadata.get('filename', '')
                if source_file not in doc_source and doc_source not in source_file:
                    match = False
            
            # 公司名过滤（使用与HybridRetriever相同的优化逻辑）
            if match and 'company' in context_filter:
                company = context_filter['company']
                doc_text = node.text.lower()
                doc_company = metadata.get('company', '').lower()
                doc_filename = (metadata.get('filename') or metadata.get('source_file', '')).lower()
                company_lower = company.lower()
                
                # 从文件名中提取公司名
                filename_company = None
                if doc_filename:
                    import re
                    clean_filename = re.sub(r'(利润表|资产负债表|现金流量表|年报|报告|财务报表|财务报告|\d{4}年?)', '', doc_filename, flags=re.IGNORECASE)
                    clean_filename = re.sub(r'年度\d+', '', clean_filename)  # 移除"年度60"等
                    clean_filename = re.sub(r'[_\-\s\.]+', '', clean_filename)
                    if len(clean_filename) >= 2:
                        filename_company = clean_filename
                
                # 优先使用文件名匹配（最准确）
                company_found = False
                
                # 1. 优先检查文件名匹配（最严格）
                if filename_company:
                    # 文件名匹配：公司名应该在文件名中，或者文件名在公司名中
                    # 使用更严格的匹配：至少匹配前3个字符
                    if len(company_lower) >= 3 and len(filename_company) >= 3:
                        # 检查前3个字符是否匹配
                        if company_lower[:3] == filename_company[:3]:
                            company_found = True
                        # 或者检查是否包含（双向）
                        elif company_lower in filename_company or filename_company in company_lower:
                            company_found = True
                    elif len(company_lower) >= 2 and len(filename_company) >= 2:
                        # 如果公司名较短，至少匹配前2个字符
                        if company_lower[:2] == filename_company[:2]:
                            company_found = True
                
                # 2. 如果文件名匹配失败，检查文档文本和元数据
                if not company_found:
                    # 检查文档文本中是否包含公司名（要求至少3个字符匹配）
                    if len(company_lower) >= 3:
                        # 在文档文本中查找公司名（要求完整匹配，避免误匹配）
                        import re
                        # 构建匹配模式：公司名前后可以有标点或空格
                        pattern = re.escape(company_lower)
                        if re.search(pattern, doc_text):
                            company_found = True
                    
                    # 检查元数据中的公司名
                    if not company_found and doc_company:
                        if company_lower in doc_company or doc_company in company_lower:
                            company_found = True
                
                if not company_found:
                    match = False
            
            # 年份过滤
            if match and 'year' in context_filter:
                filter_year = str(context_filter['year'])
                doc_year = str(metadata.get('year', ''))
                if doc_year and filter_year != doc_year:
                    match = False
            
            if match:
                filtered.append(node)
        
        return filtered
    
    def _filter_sources(self, sources: List[Dict], context_filter: Dict[str, Any]) -> List[Dict]:
        """过滤来源列表"""
        filtered = []
        for source in sources:
            metadata = source.get('metadata', {})
            match = True
            
            # 文件名过滤
            if 'filename' in context_filter:
                filename = context_filter['filename']
                doc_filename = metadata.get('filename') or metadata.get('source_file', '')
                if filename not in doc_filename and doc_filename not in filename:
                    match = False
            
            # 源文件过滤
            if match and 'source_file' in context_filter:
                source_file = context_filter['source_file']
                doc_source = metadata.get('source_file') or metadata.get('filename', '')
                if source_file not in doc_source and doc_source not in source_file:
                    match = False
            
            # 公司名过滤（使用与HybridRetriever相同的优化逻辑）
            if match and 'company' in context_filter:
                company = context_filter['company']
                doc_text = source.get('text', '').lower()
                doc_company = metadata.get('company', '').lower()
                doc_filename = (metadata.get('filename') or metadata.get('source_file', '')).lower()
                company_lower = company.lower()
                
                # 从文件名中提取公司名
                filename_company = None
                if doc_filename:
                    import re
                    clean_filename = re.sub(r'(利润表|资产负债表|现金流量表|年报|报告|财务报表|财务报告|\d{4}年?)', '', doc_filename, flags=re.IGNORECASE)
                    clean_filename = re.sub(r'年度\d+', '', clean_filename)  # 移除"年度60"等
                    clean_filename = re.sub(r'[_\-\s\.]+', '', clean_filename)
                    if len(clean_filename) >= 2:
                        filename_company = clean_filename
                
                # 优先使用文件名匹配（最准确）
                company_found = False
                
                # 1. 优先检查文件名匹配（最严格）
                if filename_company:
                    # 文件名匹配：公司名应该在文件名中，或者文件名在公司名中
                    # 使用更严格的匹配：至少匹配前3个字符
                    if len(company_lower) >= 3 and len(filename_company) >= 3:
                        # 检查前3个字符是否匹配
                        if company_lower[:3] == filename_company[:3]:
                            company_found = True
                        # 或者检查是否包含（双向）
                        elif company_lower in filename_company or filename_company in company_lower:
                            company_found = True
                    elif len(company_lower) >= 2 and len(filename_company) >= 2:
                        # 如果公司名较短，至少匹配前2个字符
                        if company_lower[:2] == filename_company[:2]:
                            company_found = True
                
                # 2. 如果文件名匹配失败，检查文档文本和元数据
                if not company_found:
                    # 检查文档文本中是否包含公司名（要求至少3个字符匹配）
                    if len(company_lower) >= 3:
                        # 在文档文本中查找公司名（要求完整匹配，避免误匹配）
                        import re
                        # 构建匹配模式：公司名前后可以有标点或空格
                        pattern = re.escape(company_lower)
                        if re.search(pattern, doc_text):
                            company_found = True
                    
                    # 检查元数据中的公司名
                    if not company_found and doc_company:
                        if company_lower in doc_company or doc_company in company_lower:
                            company_found = True
                
                if not company_found:
                    match = False
            
            # 年份过滤
            if match and 'year' in context_filter:
                filter_year = str(context_filter['year'])
                doc_year = str(metadata.get('year', ''))
                if doc_year and filter_year != doc_year:
                    match = False
            
            if match:
                filtered.append(source)
        
        return filtered
    
    def get_index_stats(self) -> Dict[str, Any]:
        """获取索引统计信息"""
        try:
            if not self.index:
                return {'status': 'not_initialized'}
            
            # 获取文档数量
            doc_count = len(self.index.docstore.docs)
            
            # 获取集合信息
            collection_count = self.chroma_collection.count() if self.chroma_collection else 0
            
            return {
                'status': 'ready',
                'document_count': doc_count,
                'vector_count': collection_count,
                'storage_dir': str(self.storage_dir),
                'collection_name': self.collection_name
            }
            
        except Exception as e:
            logger.error(f"获取索引统计失败: {str(e)}")
            return {'status': 'error', 'error': str(e)}
    
    def remove_file_from_index(self, filename: str) -> bool:
        """
        从索引中删除指定文件的所有文档
        
        Args:
            filename: 要删除的文件名
            
        Returns:
            是否成功删除
        """
        try:
            if not self.chroma_collection:
                logger.warning("⚠️ ChromaDB集合未初始化，无法删除文件索引")
                return False
            
            # 获取所有文档的ID和元数据
            existing_data = self.chroma_collection.get()
            if not existing_data or 'ids' not in existing_data:
                logger.warning(f"⚠️ 索引中没有找到文件: {filename}")
                return False
            
            # 找到属于该文件的所有文档ID
            ids_to_delete = []
            metadatas = existing_data.get('metadatas', [])
            ids = existing_data.get('ids', [])
            
            for i, metadata in enumerate(metadatas):
                if metadata and metadata.get('source_file') == filename:
                    ids_to_delete.append(ids[i])
            
            if not ids_to_delete:
                logger.info(f"ℹ️ 索引中没有找到文件 {filename} 的文档")
                return True
            
            # 删除这些文档
            self.chroma_collection.delete(ids=ids_to_delete)
            logger.info(f"✅ 从索引中删除了文件 {filename} 的 {len(ids_to_delete)} 个文档")
            
            # 如果索引已加载，需要重新加载以反映更改
            if self.index:
                try:
                    # 重新加载索引
                    self.load_existing_index()
                except Exception as e:
                    logger.warning(f"⚠️ 重新加载索引失败: {str(e)}")
                    # 如果重新加载失败，清空索引对象，下次查询时会自动加载
                    self.index = None
                    self.query_engine = None
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 删除文件索引失败: {str(e)}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return False
    
    def clear_index(self) -> bool:
        """清空索引"""
        try:
            # 删除ChromaDB集合
            if self.chroma_collection:
                self.chroma_client.delete_collection(self.collection_name)
                self.chroma_collection = self.chroma_client.create_collection(self.collection_name)
            
            # 重置索引
            self.index = None
            self.query_engine = None
            
            logger.info("✅ 索引已清空")
            return True
            
        except Exception as e:
            logger.error(f"❌ 清空索引失败: {str(e)}")
            return False
