import pytest
from utils.password_hash import get_hashed_password, verify_password


def test_password_hash():
    """测试密码哈希"""
    password = "test123"
    hashed = get_hashed_password(password)
    
    # 哈希后的密码应该与原密码不同
    assert hashed != password
    # 哈希后的密码应该是字符串
    assert isinstance(hashed, str)
    # 哈希后的密码应该有一定长度
    assert len(hashed) > 20


def test_password_verify():
    """测试密码验证"""
    password = "correct123"
    hashed = get_hashed_password(password)
    
    # 正确密码应该验证通过
    assert verify_password(password, hashed) is True
    # 错误密码应该验证失败
    assert verify_password("wrong123", hashed) is False


def test_password_hash_consistency():
    """测试密码哈希一致性"""
    password = "consistent123"
    hashed1 = get_hashed_password(password)
    hashed2 = get_hashed_password(password)
    
    # 相同密码的哈希应该不同（因为salt不同）
    assert hashed1 != hashed2
    # 但都应该能验证通过
    assert verify_password(password, hashed1) is True
    assert verify_password(password, hashed2) is True
