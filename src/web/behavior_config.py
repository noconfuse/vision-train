"""
行为检测系统统一配置文件
包含所有行为类别定义和相关配置
"""

# 行为类别定义 - 所有组件统一使用此配置
BEHAVIOR_CLASSES = {
    # 工作行为 (0-7)
    0: "研磨0.2",
    1: "装瓶称重送检", 
    2: "13mm缩分",
    3: "6mm缩分",
    4: "3mm缩分",
    5: "清扫整理",
    6: "称重烘干",
    7: "初始称重",
}

# 工作行为ID列表
WORK_BEHAVIORS = list(range(8))  # 0-7，对应8个工作行为类别

# 类别数量
NUM_CLASSES = len(BEHAVIOR_CLASSES)

# 类别名称列表（按ID顺序）
CLASS_NAMES = [BEHAVIOR_CLASSES[i] for i in range(NUM_CLASSES)]

def get_behavior_classes():
    """获取行为类别定义"""
    return BEHAVIOR_CLASSES.copy()

def get_work_behaviors():
    """获取工作行为ID列表"""
    return WORK_BEHAVIORS.copy()

def get_num_classes():
    """获取类别数量"""
    return NUM_CLASSES

def get_class_names():
    """获取类别名称列表"""
    return CLASS_NAMES.copy()

def get_class_name(class_id):
    """根据类别ID获取类别名称"""
    return BEHAVIOR_CLASSES.get(class_id, "未知")

def validate_class_id(class_id):
    """验证类别ID是否有效"""
    return class_id in BEHAVIOR_CLASSES

# 配置验证
def validate_config():
    """验证配置的一致性"""
    errors = []
    
    # 检查类别ID连续性
    expected_ids = set(range(NUM_CLASSES))
    actual_ids = set(BEHAVIOR_CLASSES.keys())
    if expected_ids != actual_ids:
        errors.append(f"类别ID不连续: 期望 {expected_ids}, 实际 {actual_ids}")
    
    # 检查工作行为ID有效性
    for work_id in WORK_BEHAVIORS:
        if not validate_class_id(work_id):
            errors.append(f"无效的工作行为ID: {work_id}")
    
    return errors

if __name__ == "__main__":
    # 配置验证
    errors = validate_config()
    if errors:
        print("❌ 配置验证失败:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("✅ 配置验证通过")
        print(f"📊 类别数量: {NUM_CLASSES}")
        print("🏷️ 行为类别:")
        for class_id, class_name in BEHAVIOR_CLASSES.items():
            print(f"  {class_id}: {class_name}")