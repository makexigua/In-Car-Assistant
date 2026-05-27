# 作用：统一暴露 task 链路的函数定义，供召回和识别阶段复用。

FUNCTION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "Open_Air_Condition",
            "description": "用户仅要打开空调或仅打开指定座位的空调。需要对指定座位进行映射，若未指定，则位置为空。",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若无指定座位，则设为空；若有指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    }
                },
                "required": [
                    "Position"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Close_Air_Condition",
            "description": "用户仅想关闭空调或仅关闭指定座位的空调。需要对指定座位进行映射，若未指定座位，则座位为空。若未指定空调，不命中此函数",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "若无指定座位，则设为空；若有指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    }
                },
                "required": [
                    "Position"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Open_Air_Condition_Defog",
            "description": "打开空调除雾除霜功能或打开指定座位的空调除雾除霜功能。需要对指定座位进行映射。指定座位可为空",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若无指定座位，则设为空；若有指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    }
                },
                "required": [
                    "Position"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Close_Air_Condition_Defog",
            "description": "关闭空调除雾除霜功能或关闭指定座位的空调除雾除霜功能。需要对指定座位进行映射。指定座位可为空",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若无指定座位，则设为空；若有指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    }
                },
                "required": [
                    "Position"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Open_Internal_Circulation",
            "description": "用户想要打开空调内循环",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Close_Internal_Circulation",
            "description": "用户想要关闭空调内循环",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Open_External_Circulation",
            "description": "用户想要打开空调外循环",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Close_External_Circulation",
            "description": "用户想要关闭空调外循环",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Set_Air_Condition_Temperature",
            "description": "按照汽车内座位位置打开空调并设置空调温度或打开空调并把空调温度调到某值或极端程度，如果某值是一个区间，从区间随便取一个数即可。Number,Ratio和Extreme只能提取一个。指定座位可为空。若仅设置空调温度也命中此函数。",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若无指定座位，则设为空；若有指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    },
                    "Number": {
                        "type": "string",
                        "description": "提取出小数、负数、正整数，不提取百分数和分数。若无则为空"
                    },
                    "Ratio": {
                        "type": "string",
                        "description": "提取出百分数和分数，并将其表示为小数。只要含百分号就为百分数。若无则为空"
                    },
                    "Extreme": {
                        "type": "string",
                        "description": "提取出包含“最”字的词组，并根据词义映射为最高或者最低的其中一个。不包含“最”字则为空"
                    }
                },
                "required": [
                    "Position",
                    "Number",
                    "Ratio",
                    "Extreme"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Inc_Air_Condition_Temperature",
            "description": "按照汽车内座位位置把空调打开并将温度调高某值，如果某值是一个区间，从区间随便取一个数即可。Number和Ratio只能提取一个。指定座位可为空。若仅调高空调温度也命中此函数。若用户说大一点、够冷了等，将NUMBER提取为1，不提取RATIO",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若无指定座位，则设为空；若有指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    },
                    "Number": {
                        "type": "string",
                        "description": "提取出小数、负数、正整数，不提取百分数和分数。若无则为空"
                    },
                    "Ratio": {
                        "type": "string",
                        "description": "提取出百分数和分数，并将其表示为小数。只要含百分号就为百分数。若无则为空"
                    }
                },
                "required": [
                    "Position",
                    "Number",
                    "Ratio"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Dec_Air_Condition_Temperature",
            "description": "按照汽车内座位位置把空调打开并将空调温度调低某值，如果某值是一个区间，从区间随便取一个数即可。Number和Ratio只能提取一个。指定座位可为空。若仅调低空调温度也命中此函数。若用户说小一点、够热了等，将NUMBER提取为1，不提取RATIO",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若无指定座位，则设为空；若有指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    },
                    "Number": {
                        "type": "string",
                        "description": "提取出小数、负数、正整数，不提取百分数和分数。若无则为空"
                    },
                    "Ratio": {
                        "type": "string",
                        "description": "提取出百分数和分数，并将其表示为小数。只要含百分号就为百分数。若无则为空"
                    }
                },
                "required": [
                    "Position",
                    "Number",
                    "Ratio"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Set_Air_Condition_Wind",
            "description": "按照汽车内座位位置设置空调风力或把空调风力调（降/升）到某值（档位）或极端程度，如果某值（某档位）是一个区间，从区间随便取一个数即可。Number,Ratio和Extreme只能提取一个。指定座位可为空",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若无指定座位，则设为空；若有指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    },
                    "Number": {
                        "type": "string",
                        "description": "提取出小数、负数、正整数，不提取百分数和分数。若无则为空"
                    },
                    "Ratio": {
                        "type": "string",
                        "description": "提取出百分数和分数，并将其表示为小数。只要含百分号就为百分数。若无则为空"
                    },
                    "Extreme": {
                        "type": "string",
                        "description": "提取出包含“最”字的词组，并根据词义映射为最高或者最低的其中一个。不包含“最”字则为空"
                    }
                },
                "required": [
                    "Position",
                    "Number",
                    "Ratio",
                    "Extreme"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Inc_Air_Condition_Wind",
            "description": "按照汽车内座位位置把空调打开并将空调风力调高某值，如果某值是一个区间，从区间随便取一个数即可，需要进行映射。Number和Ratio只能提取一个。指定座位可为空。若仅调高空调风力，也命中此函数。若用户说大一点、风不够大等，将NUMBER提取为1，不提取RATIO",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若无指定座位，则设为空；若有指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    },
                    "Number": {
                        "type": "string",
                        "description": "提取出小数、负数、正整数，不提取百分数和分数。若无则为空"
                    },
                    "Ratio": {
                        "type": "string",
                        "description": "提取出百分数和分数，并将其表示为小数。只要含百分号就为百分数。若无则为空"
                    }
                },
                "required": [
                    "Position",
                    "Number",
                    "Ratio"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Dec_Air_Condition_Wind",
            "description": "按照汽车内座位位置把空调打开并将空调风力调低某值，而非降到。如果某值是一个区间，从区间随便取一个数即可，需要进行映射。Number和Ratio只能提取一个。指定座位可为空。若仅调低空调风力，也命中此函数。若用户说小一点、够大了等，将NUMBER提取为1，不提取RATIO",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若无指定座位，则设为空；若有指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    },
                    "Number": {
                        "type": "string",
                        "description": "提取出小数、负数、正整数，不提取百分数和分数。若无则为空"
                    },
                    "Ratio": {
                        "type": "string",
                        "description": "提取出百分数和分数，并将其表示为小数。只要含百分号就为百分数。若无则为空"
                    }
                },
                "required": [
                    "Position",
                    "Number",
                    "Ratio"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Set_Wind_Direction",
            "description": "将空调向指定方向吹或让空调向指定方向吹，或打开空调指定方向吹风。需要对指定方向进行映射",
            "parameters": {
                "type": "object",
                "properties": {
                    "Direction": {
                        "type": "string",
                        "description": "仅包括吹脸、吹脚、吹脸吹脚、吹窗吹脚、吹窗"
                    }
                },
                "required": [
                    "Direction"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Cancel_Wind_Direction",
            "description": "取消将空调向指定方向吹或让空调不再向指定方向吹，需要对指定方向进行映射",
            "parameters": {
                "type": "object",
                "properties": {
                    "Direction": {
                        "type": "string",
                        "description": "仅包括吹脸、吹脚、吹脸吹脚、吹窗吹脚、吹窗"
                    }
                },
                "required": [
                    "Direction"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Open_Heated_Seat",
            "description": "打开座椅加热或打开指定座位的座椅加热。指定座位可为空。或用户说屁股和背有点冷若用户还有调整（调高/调低）座椅温度的意图，则不命中此函数",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若无指定座位，则设为空；若有指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    }
                },
                "required": [
                    "Position"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Close_Heated_Seat",
            "description": "关闭或不用开启座椅加热或关闭指定座位的座椅加热，需对指定座位进行映射。指定座位可为空",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若无指定座位，则设为空；若有指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾）即前排"
                    }
                },
                "required": [
                    "Position"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Set_Seat_Temperature",
            "description": "按照汽车内座位位置把打开（启动）座椅加热并将座椅温度调整到指定值或极端程度，如果指定值是一个区间，从区间随便取一个数即可，需要进行映射。Number,Ratio和Extreme只能提取一个。指定座位可为空。若仅调节座椅温度也命中此函数",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若无指定座位，则设为空；若有指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    },
                    "Number": {
                        "type": "string",
                        "description": "提取出小数、负数、正整数，不提取百分数和分数。若无则为空"
                    },
                    "Ratio": {
                        "type": "string",
                        "description": "提取出百分数和分数，并将其表示为小数。只要含百分号或一半等表示，就为百分数。若无则为空"
                    },
                    "Extreme": {
                        "type": "string",
                        "description": "提取出包含“最”字的词组，并根据词义映射为最高或者最低的其中一个。不包含“最”字则为空"
                    }
                },
                "required": [
                    "Position",
                    "Number",
                    "Ratio",
                    "Extreme"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Inc_Seat_Temperature",
            "description": "按照汽车内座位位置把座椅加热打开并将温度调高某值，如果某值是一个区间，从区间随便取一个数即可，需要进行映射。Number和Ratio只能提取一个。指定座位可为空。若仅调高座椅温度，也命中此函数。若用户说大一点、有点凉等，将NUMBER提取为1，不提取RATIO",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若无指定座位，则设为空；若有指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    },
                    "Number": {
                        "type": "string",
                        "description": "提取出小数、负数、正整数，不提取百分数和分数。若无则为空"
                    },
                    "Ratio": {
                        "type": "string",
                        "description": "提取出百分数和分数，并将其表示为小数。只要含百分号就为百分数。若无则为空"
                    }
                },
                "required": [
                    "Position",
                    "Number",
                    "Ratio"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Dec_Seat_Temperature",
            "description": "按照汽车内座位位置把座椅加热打开并将座椅温度调低某值，如果某值是一个区间，从区间随便取一个数即可。Number和Ratio只能提取一个。若无指定座位，则设为空。若仅调低座椅温度，也命中此函数。或用户说屁股和背太热若用户说小一点、够热了等，将NUMBER提取为1，不提取RATIO",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "若无指定座位，则设为空；若有指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    },
                    "Number": {
                        "type": "string",
                        "description": "提取出小数、负数、正整数，不提取百分数和分数。若无则为空"
                    },
                    "Ratio": {
                        "type": "string",
                        "description": "提取出百分数和分数，并将其表示为小数。只要含百分号就为百分数。若无则为空"
                    }
                },
                "required": [
                    "Position",
                    "Number",
                    "Ratio"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Open_Seat_Ventilation",
            "description": "打开座椅通风功能或打开指定座位的座椅通风功能，需对指定座位进行映射。指定座位可为空。若用户还有调整（调高/调低）座椅通风大小的意图，则不命中此函数",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若无明确的指定座位，则设为空；若有明确的指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    }
                },
                "required": [
                    "Position"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Close_Seat_Ventilation",
            "description": "关闭座椅通风功能或关闭指定座位的座椅通风功能，需对指定座位进行映射。指定座位可为空",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若无明确的指定座位，则设为空；若有明确的指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    }
                },
                "required": [
                    "Position"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Set_Seat_Ventilation",
            "description": "按照指定座位把座椅通风打开并把档位调节到或调节至指定值或极端程度，如果指定值是一个区间，从区间随便取一个数即可，需要进行映射。Number,Ratio和Extreme只能提取一个。指定座位可为空。若仅调节座椅通风档位，也命中此函数",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若无明确的指定座位，则设为空；若有明确的指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    },
                    "Number": {
                        "type": "string",
                        "description": "提取出小数、负数、正整数，不提取百分数和分数。若无则为空"
                    },
                    "Ratio": {
                        "type": "string",
                        "description": "提取出百分数和分数，并将其表示为小数。只要含百分号就为百分数。若无则为空"
                    },
                    "Extreme": {
                        "type": "string",
                        "description": "提取出包含“最”字的词组，并根据词义映射为最高或者最低的其中一个。不包含“最”字则为空"
                    }
                },
                "required": [
                    "Position",
                    "Number",
                    "Ratio",
                    "Extreme"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Inc_Seat_Ventilation",
            "description": "按照指定座位把座椅通风打开并将档位调大某值或某档位，如果某值（某档位）是一个区间，从区间随便取一个数即可，需要进行映射。Number和Ratio只能提取一个。指定座位可为空。若仅调大座椅通风也命中此函数。若用户说大一点等，将NUMBER提取为1，不提取RATIO",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若无明确的指定座位，则设为空；若有明确的指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    },
                    "Number": {
                        "type": "string",
                        "description": "提取出小数、负数、正整数，不提取百分数和分数。若无则为空"
                    },
                    "Ratio": {
                        "type": "string",
                        "description": "提取出百分数和分数，并将其表示为小数。只要含百分号就为百分数。若无则为空"
                    }
                },
                "required": [
                    "Position",
                    "Number",
                    "Ratio"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Dec_Seat_Ventilation",
            "description": "按照指定座位把座椅通风打开并将档位调小某值或某档位，如果某值（某档位）是一个区间，从区间随便取一个数即可，需要进行映射。Number和Ratio只能提取一个。指定座位可为空。若仅调低座椅通风档位，也命中此函数。若用户说小一点等，将NUMBER提取为1，不提取RATIO",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若无明确的指定座位，则设为空；若有明确的指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    },
                    "Number": {
                        "type": "string",
                        "description": "提取出小数、负数、正整数，不提取百分数和分数。若无则为空"
                    },
                    "Ratio": {
                        "type": "string",
                        "description": "提取出百分数和分数，并将其表示为小数。只要含百分号就为百分数。若无则为空"
                    }
                },
                "required": [
                    "Position",
                    "Number",
                    "Ratio"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Open_Seat_Massage",
            "description": "打开座椅按摩功能或打开指定座位的座椅按摩，需对指定座位进行映射。指定座位可为空。若用户还有调整（调高/调低）座椅按摩力度的意图，则不命中此函数",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若无明确的指定座位，则设为空；若有明确的指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    }
                },
                "required": [
                    "Position"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Close_Seat_Massage",
            "description": "关闭座椅按摩功能或关闭指定座位的座椅按摩，需对指定座位进行映射。指定座位可为空",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若无明确的指定座位，则设为空；若有明确的指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    }
                },
                "required": [
                    "Position"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Set_Seat_Massage",
            "description": "按照指定座位把座椅按摩打开并将力度调节到或调节至指定值或极端程度，如果指定值是一个区间，从区间随便取一个数即可，需要进行映射。Number,Ratio和Extreme只能提取一个。指定座位可为空。若仅调节按摩力度也命中此函数",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若无明确的指定座位，则设为空；若有明确的指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    },
                    "Number": {
                        "type": "string",
                        "description": "提取出小数、负数、正整数，不提取百分数和分数。若无则为空"
                    },
                    "Ratio": {
                        "type": "string",
                        "description": "提取出百分数和分数，并将其表示为小数。只要含百分号就为百分数。若无则为空"
                    },
                    "Extreme": {
                        "type": "string",
                        "description": "提取出包含“最”字的词组，并根据词义映射为最高或者最低的其中一个。不包含“最”字则为空"
                    }
                },
                "required": [
                    "Position",
                    "Number",
                    "Ratio",
                    "Extreme"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Inc_Seat_Massage",
            "description": "按照指定座位把座椅按摩打开并将力度调大某值或某档位，如果某值（某档位）是一个区间，从区间随便取一个数即可，需要进行映射。Number和Ratio只能提取一个。指定座位可为空。若仅调大座椅按摩力度也命中此函数。若用户说大一点，不够舒服等，将NUMBER提取为1，不提取RATIO",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若无明确的指定座位，则设为空；若有明确的指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    },
                    "Number": {
                        "type": "string",
                        "description": "提取出小数、负数、正整数，不提取百分数和分数。若无则为空"
                    },
                    "Ratio": {
                        "type": "string",
                        "description": "提取出百分数和分数，并将其表示为小数。只要含百分号就为百分数。若无则为空"
                    }
                },
                "required": [
                    "Position",
                    "Number",
                    "Ratio"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Dec_Seat_Massage",
            "description": "按照指定座位把座椅按摩打开并将按摩力度调小某值或某档位，如果某值（某档位）是一个区间，从区间随便取一个数即可，需要进行映射。Number和Ratio只能提取一个。指定座位可为空。若仅调低座椅按摩力度，也命中此函数。若用户说小一点等，将NUMBER提取为1，不提取RATIO",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若无明确的指定座位，则设为空；若有明确的指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    },
                    "Number": {
                        "type": "string",
                        "description": "提取出小数、负数、正整数，不提取百分数和分数。若无则为空"
                    },
                    "Ratio": {
                        "type": "string",
                        "description": "提取出百分数和分数，并将其表示为小数。只要含百分号就为百分数。若无则为空"
                    }
                },
                "required": [
                    "Position",
                    "Number",
                    "Ratio"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Open_Heated_Steer",
            "description": "用户需要打开对方向盘的加热功能",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Close_Heated_Steer",
            "description": "用户需要关闭对方向盘的加热功能",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Set_Steer_Temperature",
            "description": "把方向盘温度调到指定值或极端程度，如果指定值是一个区间，从区间随便取一个数即可。Number,Ratio和Extreme只能提取一个",
            "parameters": {
                "type": "object",
                "properties": {
                    "Number": {
                        "type": "string",
                        "description": "提取出小数、负数、正整数，不提取百分数和分数。若无则为空"
                    },
                    "Ratio": {
                        "type": "string",
                        "description": "提取出百分数和分数，并将其表示为小数。只要含百分号就为百分数。若无则为空"
                    },
                    "Extreme": {
                        "type": "string",
                        "description": "提取出包含“最”字的词组，并映射为最高或者最低的其中一个。不包含“最”字则为空"
                    }
                },
                "required": [
                    "Number",
                    "Ratio",
                    "Extreme"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Inc_Steer_Temperature",
            "description": "按照数字把方向盘温度调高",
            "parameters": {
                "type": "object",
                "properties": {
                    "Number": {
                        "type": "string",
                        "description": "提取出小数、负数、正整数，不提取百分数和分数。若无则为空"
                    },
                    "Ratio": {
                        "type": "string",
                        "description": "提取出百分数和分数，并将其表示为小数。只要含百分号就为百分数。若无则为空"
                    }
                },
                "required": [
                    "Number",
                    "Ratio"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Dec_Steer_Temperature",
            "description": "按照数字把方向盘温度调低某值，如果某值是一个区间，从区间随便取一个数即可",
            "parameters": {
                "type": "object",
                "properties": {
                    "Number": {
                        "type": "string",
                        "description": "提取出小数、负数、正整数，不提取百分数和分数。若无则为空"
                    },
                    "Ratio": {
                        "type": "string",
                        "description": "提取出百分数和分数，并将其表示为小数。只要含百分号就为百分数。若无则为空"
                    }
                },
                "required": [
                    "Number",
                    "Ratio"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Open_HUD",
            "description": "打开投影或HUD，即用户要使用抬头显示器",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Close_HUD",
            "description": "关闭投影或HUD，即不使用抬头显示器",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Adjust_Hud_Brightness",
            "description": "调节HUD屏幕的亮度，有1，2，3，4，5个档位,亮一点按照1个档位增加，最多不超过5档，暗一点按照1个档位减少，最低不低于1档",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {
                        "type": "string",
                        "description": "亮度档位，有1，2，3，4，5个档位"
                    }
                },
                "required": [
                    "level"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Inc_HUD_Brightness",
            "description": "调高HUD的亮度",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Dec_HUD_Brightness",
            "description": "调低HUD的亮度",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Open_Dormer",
            "description": "打开天窗，即打开位于车顶的那扇窗户",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Close_Dormer",
            "description": "关闭天窗，即关闭位于车顶的那扇窗户",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Open_Window",
            "description": "按照车内位置来打开车窗。指定座位可为空。若用户还有调整车窗开合大小的意思，不命中此函数",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若无指定座位，则设为空；若有指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    }
                },
                "required": [
                    "Position"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Close_Window",
            "description": "按照车内位置来关闭车窗。指定座位可为空",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若无指定座位，则设为空；若有指定座位，将其映射为主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有的其中一个。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    }
                },
                "required": [
                    "Position"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Set_Window",
            "description": "按照指定位置和百分数来打开车窗并调整车窗开合大小。指定座位可为空。若仅调整车窗开合大小，也命中此函数",
            "parameters": {
                "type": "object",
                "properties": {
                    "Position": {
                        "type": "string",
                        "description": "指定座位。若没有指定座位，则设为空；若有指定座位，必须将其映射为以下选项的其中一个：主驾、副驾、前排、后排、右侧、左侧、右后、左后、主对角、副对角、所有。主对角必须同时包括主驾和后排右边的两个座位；副对角必须同时包括副驾和后排左边的两个座位；左侧包括主驾座位和后排左边的两个座位；右侧包括副驾座位和后排右边的两个座位；左后代表后排左边座位，即主驾后面的座位；右后代表后排右边座位，即副驾后面的座位主副驾（主驾和副驾），即前排"
                    },
                    "Ratio": {
                        "type": "string",
                        "description": "仅包括百分数和分数，并表示为小数"
                    }
                },
                "required": [
                    "Position",
                    "Ratio"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Open_Sunshade",
            "description": "打开遮阳帘或把遮阳帘往下放，或用户觉得开车时太阳很晃眼睛",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Close_Sunshade",
            "description": "关闭遮阳帘或把遮阳帘收起或拉上去或卷起来，或用户觉得开车时遮阳帘很挡视线",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Open_Trunk",
            "description": "打开汽车的后备箱或尾门，或者用户想要在车上放大件行李",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Close_Trunk",
            "description": "关闭汽车的后备箱或尾门",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Open_Wiper",
            "description": "打开雨刷器或用户觉得在挡风玻璃上的雨水很挡视线",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Close_Wiper",
            "description": "关闭雨刷器或用户觉得雨刷器有点晃眼睛",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Open_Headlamp",
            "description": "打开车前照明的大灯",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Close_Headlamp",
            "description": "关闭车前照明的大灯",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Open_High_Beam",
            "description": "打开远光灯，即打开很黑暗或照明条件不好的环境中能提高可见度的灯光",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Close_High_Beam",
            "description": "关闭远光灯，即关闭很黑暗或照明条件不好环境中能提高可见度的灯光",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Open_Low_Beam",
            "description": "打开近光灯或低束灯，即打开夜晚照明条件良好环境中使用的灯光",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Close_Low_Beam",
            "description": "关闭近光灯，即关闭夜晚照明条件良好环境中使用的灯光",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Open_Front_Fog_Light",
            "description": "只打开前雾灯，即打开位于车辆前部的雾灯",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Close_Front_Fog_Light",
            "description": "只关闭前雾灯，即关闭位于车辆前部的雾灯",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Open_Back_Fog_Light",
            "description": "只打开后雾灯，即打开位于车辆后部的雾灯",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Close_Back_Fog_Light",
            "description": "只关闭后雾灯，即关闭位于车辆后部的雾灯",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Open_Reading_Light",
            "description": "打开阅读灯",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Close_Reading_Light",
            "description": "关闭阅读灯",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Open_AutoHold",
            "description": "用户想要打开汽车的自动驻车功能，即想要停车时不再控制刹车",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Close_AutoHold",
            "description": "用户想要关闭汽车的自动驻车功能，即想要自己控制刹车",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Open_Engine_AutoStop",
            "description": "用户想要打开汽车的自动启停功能，即短暂停车等待时自动熄火",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Close_Engine_AutoStop",
            "description": "用户想要关闭汽车的自动启停功能，即短暂停车时不再熄火",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Set_Driving_Mode",
            "description": "询问驾驶模式或将汽车驾驶模式设为指定的驾驶模式，需要进行映射",
            "parameters": {
                "type": "object",
                "properties": {
                    "Mode": {
                        "type": "string",
                        "description": "仅包括经济模式、舒适模式、运动模式和正常模式。若无则为空"
                    }
                },
                "required": [
                    "Mode"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Open_DashCam",
            "description": "打开车里的行车记录仪，或打开行车记录仪的界面（APP）",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Close_DashCam",
            "description": "关闭车里的行车记录仪，或关闭行车记录仪的界面（APP）",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Record_Audio",
            "description": "用户要求开始录音，即让行车记录仪记录车内的所有声音",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Stop_Audio",
            "description": "用户要求停止录音，即让行车记录仪结束记录车内声音",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Record_Video",
            "description": "用户要求开始录像，即让行车记录仪持续记录画面",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Stop_Video",
            "description": "用户要求停止录像，即让行车记录仪不再持续记录视频画面",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Take_Photo",
            "description": "用户要求拍照，即让行车记录仪保存下当前画面",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Open_Bluetooth",
            "description": "打开车里的蓝牙",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Close_Bluetooth",
            "description": "关闭车里的蓝牙",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Open_ScreenCast",
            "description": "打开投屏或视频投射，即用户想用车载屏观看手机上的内容",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Close_ScreenCast",
            "description": "关闭当前投屏或视频投射",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Open_Sound_Volume",
            "description": "按照声音来源把相应音源的声音打开，即解除静音。若未指定声音来源就将声音来源设为空",
            "parameters": {
                "type": "object",
                "properties": {
                    "Sound_Source": {
                        "type": "string",
                        "description": "仅包括导航、电话、媒体、通知、语音和所有。若无则为空"
                    }
                },
                "required": [
                    "Sound_Source"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Set_Sound_Volume",
            "description": "按照声音来源和数字把相应音源的声音调到某值，但不是调到最大或最小。若未指定声音来源就将声音来源设为空。Number和Ratio只能提取一个",
            "parameters": {
                "type": "object",
                "properties": {
                    "Sound_Source": {
                        "type": "string",
                        "description": "仅包括导航、电话、媒体、通知、语音和所有。若无则为空"
                    },
                    "Number": {
                        "type": "string",
                        "description": "提取出小数、负数、正整数，不提取百分数和分数。若无则为空"
                    },
                    "Ratio": {
                        "type": "string",
                        "description": "提取出百分数和分数，并将其表示为小数。只要含百分号就为百分数。若无则为空"
                    }
                },
                "required": [
                    "Sound_Source",
                    "Number",
                    "Ratio"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Set_Sound_Volume_Max",
            "description": "按照声音来源把相应音源的声音调到最高。若未指定声音来源就将声音来源设为空",
            "parameters": {
                "type": "object",
                "properties": {
                    "Sound_Source": {
                        "type": "string",
                        "description": "仅包括导航、电话、媒体、通知、语音和所有。若无则为空"
                    }
                },
                "required": [
                    "Sound_Source"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Inc_Sound_Volume",
            "description": "按照声音来源和数字把相应音源的声音调高某值。若未指定声音来源则把声音来源设为空。Number和Ratio只能提取一个。只有用户明确指定要调高音量时，才命中此类",
            "parameters": {
                "type": "object",
                "properties": {
                    "Sound_Source": {
                        "type": "string",
                        "description": "声音来源，仅包括导航、电话、媒体、通知、语音和所有。若无则为空"
                    },
                    "Number": {
                        "type": "string",
                        "description": "提取出小数、负数、正整数，不提取百分数和分数。若无则为空"
                    },
                    "Ratio": {
                        "type": "string",
                        "description": "提取出百分数和分数，并将其表示为小数。只要含百分号就为百分数。若无则为空"
                    }
                },
                "required": [
                    "Sound_Source",
                    "Number",
                    "Ratio"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Dec_Sound_Volume",
            "description": "按照声音来源和数字把相应音源的声音调低某值。若未指定声音来源就将声音来源设为空。Number和Ratio只能提取一个。只有用户明确指定要调低音量，才命中此类",
            "parameters": {
                "type": "object",
                "properties": {
                    "Sound_Source": {
                        "type": "string",
                        "description": "声音来源，仅包括导航、电话、媒体、通知、语音和所有。若无则为空"
                    },
                    "Number": {
                        "type": "string",
                        "description": "提取出小数、负数、正整数，不提取百分数和分数。若无则为空"
                    },
                    "Ratio": {
                        "type": "string",
                        "description": "提取出百分数和分数，并将其表示为小数。只要含百分号就为百分数。若无则为空"
                    }
                },
                "required": [
                    "Sound_Source",
                    "Number",
                    "Ratio"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Set_Brightness",
            "description": "按照数字把系统亮度或屏幕亮度调到某值，如果某值是一个区间，从区间随便取一个数即可。Number和Ratio只能提取一个",
            "parameters": {
                "type": "object",
                "properties": {
                    "Number": {
                        "type": "string",
                        "description": "提取出小数、负数、正整数，不提取百分数和分数。若无则为空"
                    },
                    "Ratio": {
                        "type": "string",
                        "description": "提取出百分数和分数，并将其表示为小数。只要含百分号就为百分数。若无则为空"
                    }
                },
                "required": [
                    "Number",
                    "Ratio"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Set_Brightness_Min",
            "description": "把系统亮度或屏幕亮度调到最低",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Inc_Brightness",
            "description": "按照数字把系统亮度或屏幕亮度调高调大，而不是调到某值，如果某值是一个区间，从区间随便取一个数即可。Number和Ratio只能提取一个",
            "parameters": {
                "type": "object",
                "properties": {
                    "Number": {
                        "type": "string",
                        "description": "提取出小数、负数、正整数，不提取百分数和分数。若无则为空"
                    },
                    "Ratio": {
                        "type": "string",
                        "description": "提取出百分数和分数，并将其表示为小数。只要含百分号就为百分数。若无则为空"
                    }
                },
                "required": [
                    "Number",
                    "Ratio"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Dec_Brightness",
            "description": "按照数字把系统亮度调低某值，但不是调到最低，如果某值是一个区间，从区间随便取一个数即可。Number和Ratio只能提取一个。若用户说小一点、够亮了等，将NUMBER提取为1，不提取RATIO",
            "parameters": {
                "type": "object",
                "properties": {
                    "Number": {
                        "type": "string",
                        "description": "提取出小数、负数、正整数，不提取百分数和分数。若无则为空"
                    },
                    "Ratio": {
                        "type": "string",
                        "description": "提取出百分数和分数，并将其表示为小数。只要含百分号就为百分数。若无则为空"
                    }
                },
                "required": [
                    "Number",
                    "Ratio"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Sync_Contact",
            "description": "用户想要同步联系人或更新通讯录",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Call_Phone",
            "description": "用户需要打电话",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Call_Phone_By_Contact",
            "description": "给指定联系人拨打电话",
            "parameters": {
                "type": "object",
                "properties": {
                    "Contact": {
                        "type": "string",
                        "description": "联系人，包括但不限于爸爸、妈妈等"
                    }
                },
                "required": [
                    "Contact"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Call_Number",
            "description": "拨打指定电话",
            "parameters": {
                "type": "object",
                "properties": {
                    "Phone_Number": {
                        "type": "string",
                        "description": "国内标准为11位数字组成的普通号码或7-8位数字组成的座机号码"
                    }
                },
                "required": [
                    "Phone_Number"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Answer_Phone",
            "description": "接听电话，即接通来电",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Reject_Phone",
            "description": "拒接电话，即挂断还未接听的来电",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "View_Send_Record",
            "description": "查看用户给别人打电话的拨打记录",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "View_Already_Call",
            "description": "用户想要查看已经接通的电话记录",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "View_Not_Call",
            "description": "用户想要查看没接到的电话记录",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Unknown",
            "description": "无意义的，或未指明部件的命令（如\"打开这个\"\"关了吧\"），或属于闲聊、问候、开玩笑、询问歌曲演唱者、百科知识、娱乐知识、生活知识、诗词、数学运算、单位换算、音乐推荐、人物介绍、笑话、翻译等。注意：导航、路线规划、查天气、搜地点、查景点详情等有明确地点的查询不属于此类。",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]


def register_mcp_tools(tools: list[dict]) -> None:
    """向 FUNCTION_TOOLS 中追加 MCP 工具定义（由 mcp_executor.init_mcp 调用）。"""
    for tool in tools:
        name = tool.get("function", {}).get("name", "")
        # 同名替换，避免重复注册
        replaced = False
        for i, existing in enumerate(FUNCTION_TOOLS):
            if existing.get("function", {}).get("name") == name:
                FUNCTION_TOOLS[i] = tool
                replaced = True
                break
        if not replaced:
            FUNCTION_TOOLS.append(tool)
