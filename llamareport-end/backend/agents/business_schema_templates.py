"""
Business schema templates used for business highlights pipeline.
"""

from typing import Dict, Any, List

from models.business_schema import TemplateLibrary, IndustryTemplate


BUSINESS_SCHEMA_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "banking": {
        "industry": "banking",
        "template_version": "1.0.0",
        "template_name": "银行业-三板块拆分",
        "description": "零售/对公/同业三大板块",
        "industry_clues": [
            "吸收公众存款",
            "发放贷款",
            "净息差",
            "不良率"
        ],
        "segments": [
            {
                "segment_id": "retail_banking",
                "segment_name": "零售银行业务",
                "business_scope": "面向个人及小微客户的存贷款与财富管理",
                "typical_products_or_services": [
                    "住房按揭贷款",
                    "消费贷款",
                    "信用卡",
                    "个人理财",
                    "私人银行"
                ],
                "core_financial_metrics": {
                    "scale": [
                        "零售营业收入",
                        "个人贷款余额",
                        "零售AUM"
                    ],
                    "profitability": [
                        "零售净利润",
                        "零售净息差"
                    ],
                    "risk": [
                        "零售不良率",
                        "信用卡不良率",
                        "零售减值损失"
                    ],
                    "efficiency": [
                        "客户数",
                        "MAU",
                        "线上交易占比"
                    ]
                },
                "strategic_signals": [
                    "高风险资产压降",
                    "抵押类贷款占比变化",
                    "财富管理客户增长"
                ],
                "common_risks": [
                    "宏观消费下行",
                    "个人客户还款能力恶化"
                ],
                "long_term_role": "长期利润核心，但周期波动大"
            },
            {
                "segment_id": "corporate_banking",
                "segment_name": "对公银行业务",
                "business_scope": "面向企业和政府客户的融资与结算服务",
                "typical_products_or_services": [
                    "企业贷款",
                    "供应链金融",
                    "现金管理",
                    "跨境结算"
                ],
                "core_financial_metrics": {
                    "scale": [
                        "企业贷款余额",
                        "对公客户数"
                    ],
                    "profitability": [
                        "对公利息收入",
                        "中间业务收入"
                    ],
                    "risk": [
                        "企业不良率",
                        "行业集中度"
                    ],
                    "efficiency": [
                        "单客户综合收益",
                        "结算渗透率"
                    ]
                },
                "strategic_signals": [
                    "新兴行业投向",
                    "政策支持领域占比"
                ],
                "common_risks": [
                    "行业周期波动",
                    "房地产与地方融资风险"
                ],
                "long_term_role": "规模稳定器与政策红利承接者"
            },
            {
                "segment_id": "interbank_treasury",
                "segment_name": "同业与资金业务",
                "business_scope": "金融市场与同业交易相关业务",
                "typical_products_or_services": [
                    "债券投资",
                    "同业存放",
                    "外汇及衍生品"
                ],
                "core_financial_metrics": {
                    "scale": [
                        "投资类金融资产规模"
                    ],
                    "profitability": [
                        "投资收益",
                        "其他非息收入"
                    ],
                    "risk": [
                        "市场风险敞口",
                        "利率风险"
                    ],
                    "efficiency": [
                        "交易量",
                        "市场份额"
                    ]
                },
                "strategic_signals": [
                    "非息收入占比提升",
                    "交易能力排名"
                ],
                "common_risks": [
                    "市场波动",
                    "估值回撤"
                ],
                "long_term_role": "周期对冲器与收益平滑器"
            }
        ]
    },
    "insurance": {
        "industry": "insurance",
        "template_version": "1.0.0",
        "template_name": "保险业-寿险为主",
        "description": "寿险/健康险等长期业务",
        "industry_clues": [
            "保费收入",
            "新单保费",
            "内含价值"
        ],
        "segments": [
            {
                "segment_id": "life_insurance",
                "segment_name": "寿险业务",
                "business_scope": "长期人身保障与储蓄型保险",
                "typical_products_or_services": [
                    "长期寿险",
                    "年金险",
                    "健康险"
                ],
                "core_financial_metrics": {
                    "scale": [
                        "保费收入",
                        "新单保费"
                    ],
                    "profitability": [
                        "内含价值",
                        "剩余边际"
                    ],
                    "risk": [
                        "退保率",
                        "负债久期错配"
                    ],
                    "efficiency": [
                        "代理人产能"
                    ]
                },
                "strategic_signals": [
                    "长期险占比",
                    "价值率变化"
                ],
                "common_risks": [
                    "利率下行",
                    "代理人流失"
                ],
                "long_term_role": "长期价值核心"
            }
        ]
    },
    "securities": {
        "industry": "securities",
        "template_version": "1.0.0",
        "template_name": "证券业-经纪业务",
        "description": "证券交易服务为主",
        "industry_clues": [
            "经纪业务",
            "佣金收入",
            "两融"
        ],
        "segments": [
            {
                "segment_id": "brokerage",
                "segment_name": "经纪业务",
                "business_scope": "证券交易服务",
                "typical_products_or_services": [
                    "股票交易",
                    "两融"
                ],
                "core_financial_metrics": {
                    "scale": [
                        "成交额"
                    ],
                    "profitability": [
                        "佣金收入"
                    ],
                    "risk": [
                        "两融风险"
                    ],
                    "efficiency": [
                        "客户数"
                    ]
                },
                "strategic_signals": [
                    "佣金率变化"
                ],
                "common_risks": [
                    "市场低迷"
                ],
                "long_term_role": "基础现金流来源"
            }
        ]
    },
    "manufacturing": {
        "industry": "manufacturing",
        "template_version": "1.0.0",
        "template_name": "制造业-核心产品线",
        "description": "核心产品与产能驱动",
        "industry_clues": [
            "产能利用率",
            "产量",
            "生产线"
        ],
        "segments": [
            {
                "segment_id": "core_products",
                "segment_name": "核心产品线",
                "business_scope": "公司主要产品",
                "typical_products_or_services": [
                    "产品A",
                    "产品B"
                ],
                "core_financial_metrics": {
                    "scale": [
                        "产品收入"
                    ],
                    "profitability": [
                        "毛利率"
                    ],
                    "risk": [
                        "库存"
                    ],
                    "efficiency": [
                        "产能利用率"
                    ]
                },
                "strategic_signals": [
                    "产品结构升级"
                ],
                "common_risks": [
                    "需求波动"
                ],
                "long_term_role": "收入与利润基础"
            }
        ]
    },
    "internet_platform": {
        "industry": "internet_platform",
        "template_version": "1.0.0",
        "template_name": "互联网平台-C端业务",
        "description": "用户增长与变现为主",
        "industry_clues": [
            "MAU",
            "DAU",
            "流量"
        ],
        "segments": [
            {
                "segment_id": "c_end_business",
                "segment_name": "C端业务",
                "business_scope": "面向个人用户的服务",
                "typical_products_or_services": [
                    "广告",
                    "会员"
                ],
                "core_financial_metrics": {
                    "scale": [
                        "MAU"
                    ],
                    "profitability": [
                        "ARPU"
                    ],
                    "risk": [
                        "获客成本"
                    ],
                    "efficiency": [
                        "留存率"
                    ]
                },
                "strategic_signals": [
                    "变现率变化"
                ],
                "common_risks": [
                    "流量见顶"
                ],
                "long_term_role": "增长引擎"
            }
        ]
    },
    "service": {
        "industry": "service",
        "template_version": "1.0.0",
        "template_name": "服务业-核心服务",
        "description": "医疗/教育/连锁等服务型业务",
        "industry_clues": [
            "诊疗服务",
            "培训课程",
            "门店"
        ],
        "segments": [
            {
                "segment_id": "core_services",
                "segment_name": "核心服务",
                "business_scope": "核心诊疗/教学服务",
                "typical_products_or_services": [
                    "诊疗服务",
                    "培训课程"
                ],
                "core_financial_metrics": {
                    "scale": [
                        "收入"
                    ],
                    "profitability": [
                        "毛利率"
                    ],
                    "risk": [
                        "政策依赖"
                    ],
                    "efficiency": [
                        "单人产出"
                    ]
                },
                "strategic_signals": [
                    "高端化"
                ],
                "common_risks": [
                    "政策调整"
                ],
                "long_term_role": "稳定现金流"
            }
        ]
    },
    "general_corporate": {
        "industry": "general_corporate",
        "template_version": "1.0.0",
        "template_name": "通用工商企业-核心业务",
        "description": "无法归类时的通用模板",
        "industry_clues": [],
        "segments": [
            {
                "segment_id": "core_business",
                "segment_name": "核心业务",
                "business_scope": "主要收入来源",
                "typical_products_or_services": [],
                "core_financial_metrics": {
                    "scale": [
                        "营业收入"
                    ],
                    "profitability": [
                        "净利润"
                    ],
                    "risk": [
                        "现金流"
                    ],
                    "efficiency": [
                        "ROE"
                    ]
                },
                "strategic_signals": [],
                "common_risks": [],
                "long_term_role": "公司价值核心"
            }
        ]
    }
}


def get_business_schema(industry: str) -> Dict[str, Any]:
    return BUSINESS_SCHEMA_TEMPLATES.get(industry, BUSINESS_SCHEMA_TEMPLATES["general_corporate"])


def get_template_library() -> TemplateLibrary:
    templates: List[IndustryTemplate] = []
    for template_data in BUSINESS_SCHEMA_TEMPLATES.values():
        templates.append(IndustryTemplate.model_validate(template_data))
    return TemplateLibrary(
        library_version="1.0.0",
        templates=templates
    )

