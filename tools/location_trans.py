
def transform_location(chinese_city):
    if not chinese_city:
        return chinese_city
    # 中文到英文的城市名映射表（覆盖 airports_data 中的主要城市）
    city_dict = {
        # 中国
        '北京': 'Beijing', '上海': 'Shanghai', '广州': 'Guangzhou', '深圳': 'Shenzhen',
        '成都': 'Chengdu', '杭州': 'Hangzhou', '重庆': 'Chongqing', '西安': 'Xian',
        '武汉': 'Wuhan', '南京': 'Nanjing', '昆明': 'Kunming', '天津': 'Tianjin',
        '青岛': 'Qingdao', '厦门': 'Xiamen', '长沙': 'Changsha', '大连': 'Dalian',
        '三亚': 'Sanya', '沈阳': 'Shenyang', '济南': 'Jinan', '郑州': 'Zhengzhou',
        '福州': 'Fuzhou', '南昌': 'Nanchang', '合肥': 'Hefei', '宁波': 'Ningbo',
        '哈尔滨': 'Harbin', '苏州': 'Suzhou', '无锡': 'Wuxi', '珠海': 'Zhuhai',
        '海口': 'Haikou', '贵阳': 'Guiyang', '南宁': 'Nanning', '兰州': 'Lanzhou',
        '西宁': 'Xining', '银川': 'Yinchuan', '呼和浩特': 'Hohhot', '石家庄': 'Shijiazhuang',
        '太原': 'Taiyuan', '长春': 'Changchun', '温州': 'Wenzhou', '东莞': 'Dongguan',
        '佛山': 'Foshan', '常州': 'Changzhou', '嘉兴': 'Jiaxing', '绍兴': 'Shaoxing',
        '烟台': 'Yantai', '洛阳': 'Luoyang', '泉州': 'Quanzhou',
        '香港': 'Hong Kong', '澳门': 'Macau', '台北': 'Taipei', '高雄': 'Kaohsiung',
        '台中': 'Taichung',
        # 日本 / 韩国
        '东京': 'Tokyo', '大阪': 'Osaka', '名古屋': 'Nagoya', '首尔': 'Seoul',
        '釜山': 'Busan',
        # 东南亚
        '曼谷': 'Bangkok', '新加坡': 'Singapore', '吉隆坡': 'Kuala Lumpur',
        '清迈': 'Chiang Mai', '普吉': 'Phuket', '巴厘岛': 'Bali', '雅加达': 'Jakarta',
        '河内': 'Hanoi', '胡志明市': 'Ho Chi Minh City', '金边': 'Phnom Penh',
        '暹粒': 'Siem Reap', '马尼拉': 'Manila', '宿务': 'Cebu', '仰光': 'Yangon',
        '槟城': 'Penang', '岘港': 'Da Nang',
        # 欧洲
        '巴黎': 'Paris', '伦敦': 'London', '罗马': 'Rome', '米兰': 'Milan',
        '法兰克福': 'Frankfurt', '柏林': 'Berlin', '慕尼黑': 'Munich', '维也纳': 'Vienna',
        '苏黎世': 'Zurich', '巴塞尔': 'Basel', '日内瓦': 'Geneva', '马德里': 'Madrid',
        '巴塞罗那': 'Barcelona', '里斯本': 'Lisbon', '莫斯科': 'Moscow',
        '圣彼得堡': 'Saint Petersburg', '伊斯坦布尔': 'Istanbul', '雅典': 'Athens',
        '阿姆斯特丹': 'Amsterdam', '布鲁塞尔': 'Brussels', '哥本哈根': 'Copenhagen',
        '斯德哥尔摩': 'Stockholm', '奥斯陆': 'Oslo', '赫尔辛基': 'Helsinki',
        '都柏林': 'Dublin', '华沙': 'Warsaw', '布拉格': 'Prague', '里加': 'Riga',
        '爱丁堡': 'Edinburgh', '杜塞尔多夫': 'Dusseldorf', '汉堡': 'Hamburg',
        '马赛': 'Marseille',
        # 美洲
        '纽约': 'New York', '洛杉矶': 'Los Angeles', '旧金山': 'San Francisco',
        '芝加哥': 'Chicago', '西雅图': 'Seattle', '波士顿': 'Boston',
        '华盛顿': 'Washington D.C.', '拉斯维加斯': 'Las Vegas', '迈阿密': 'Miami',
        '奥兰多': 'Orlando', '休斯顿': 'Houston', '达拉斯': 'Dallas', '丹佛': 'Denver',
        '亚特兰大': 'Atlanta', '多伦多': 'Toronto', '温哥华': 'Vancouver',
        '蒙特利尔': 'Montreal', '墨西哥城': 'Mexico City', '圣保罗': 'Sao Paulo',
        '里约热内卢': 'Rio de Janeiro', '布宜诺斯艾利斯': 'Buenos Aires',
        '利马': 'Lima', '波哥大': 'Bogota', '圣地亚哥': 'Santiago',
        '加拉加斯': 'Caracas', '圣萨尔瓦多': 'San Salvador', '檀香山': 'Honolulu',
        '卡尔加里': 'Calgary', '明尼阿波利斯': 'Minneapolis',
        '盐湖城': 'Salt Lake City', '圣迭戈': 'San Diego', '坦帕': 'Tampa',
        '纽瓦克': 'Newark', '底特律': 'Detroit', '夏洛特': 'Charlotte', '坎昆': 'Cancun',
        # 大洋洲
        '悉尼': 'Sydney', '墨尔本': 'Melbourne', '布里斯班': 'Brisbane',
        '珀斯': 'Perth', '奥克兰': 'Auckland', '帕皮提': 'Papeete', '维多利亚': 'Victoria',
        # 中东 / 非洲 / 南亚
        '迪拜': 'Dubai', '多哈': 'Doha', '开罗': 'Cairo', '约翰内斯堡': 'Johannesburg',
        '内罗毕': 'Nairobi', '开普敦': 'Cape Town', '孟买': 'Mumbai',
        '新德里': 'New Delhi', '达卡': 'Dhaka', '科威特城': 'Kuwait City',
    }

    # Check if the input is in Chinese
    if all('\u4e00' <= char <= '\u9fff' for char in chinese_city):
        return city_dict.get(chinese_city, chinese_city)
    else:
        return chinese_city
