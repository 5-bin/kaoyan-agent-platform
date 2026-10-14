-- school_detail 种子（计算机相关专业复试线参考，数据为 2025 年大致区间）
-- 用法：mysql -uroot -p kaoyan < V6_school_detail_seed.sql
SET NAMES utf8mb4;
DELETE FROM `school_detail`;

-- 用子查询按 school.name 找 school_id
INSERT INTO `school_detail` (`school_id`, `major_name`, `major_code`, `year`, `enrollment_count`, `score_line`, `remark`)
SELECT id, '计算机科学与技术', '081200', 2025, 40, 320, '学硕，408 统考' FROM `school` WHERE name='清华大学'
UNION ALL SELECT id, '软件工程', '083500', 2025, 25, 315, '学硕' FROM `school` WHERE name='清华大学'
UNION ALL SELECT id, '计算机技术', '085404', 2025, 60, 300, '专硕' FROM `school` WHERE name='清华大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 50, 310, '408 统考' FROM `school` WHERE name='北京大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 80, 300, '专硕' FROM `school` WHERE name='北京大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 60, 300, '408 统考' FROM `school` WHERE name='北京航空航天大学'
UNION ALL SELECT id, '软件工程', '083500', 2025, 30, 295, '' FROM `school` WHERE name='北京航空航天大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 55, 290, '408 统考' FROM `school` WHERE name='北京理工大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 90, 285, '专硕' FROM `school` WHERE name='北京理工大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 40, 295, '408 统考' FROM `school` WHERE name='北京邮电大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 120, 280, '专硕扩招' FROM `school` WHERE name='北京邮电大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 30, 305, '408 统考' FROM `school` WHERE name='中国人民大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 45, 315, '408 统考' FROM `school` WHERE name='复旦大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 70, 300, '' FROM `school` WHERE name='复旦大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 60, 320, '408 统考' FROM `school` WHERE name='上海交通大学'
UNION ALL SELECT id, '软件工程', '083500', 2025, 40, 310, '' FROM `school` WHERE name='上海交通大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 100, 300, '' FROM `school` WHERE name='上海交通大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 50, 300, '408 统考' FROM `school` WHERE name='同济大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 80, 290, '' FROM `school` WHERE name='同济大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 35, 300, '408 统考' FROM `school` WHERE name='华东师范大学'
UNION ALL SELECT id, '软件工程', '083500', 2025, 25, 290, '' FROM `school` WHERE name='华东师范大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 40, 290, '408 统考' FROM `school` WHERE name='华东理工大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 50, 305, '408 统考' FROM `school` WHERE name='南开大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 60, 290, '' FROM `school` WHERE name='南开大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 55, 300, '408 统考' FROM `school` WHERE name='天津大学'
UNION ALL SELECT id, '软件工程', '083500', 2025, 30, 290, '' FROM `school` WHERE name='天津大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 50, 290, '408 统考' FROM `school` WHERE name='重庆大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 70, 280, '' FROM `school` WHERE name='重庆大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 40, 270, '专硕为主' FROM `school` WHERE name='重庆邮电大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 200, 260, '招生大户' FROM `school` WHERE name='重庆邮电大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 45, 290, '408 统考' FROM `school` WHERE name='大连理工大学'
UNION ALL SELECT id, '软件工程', '083500', 2025, 30, 280, '' FROM `school` WHERE name='大连理工大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 50, 285, '408 统考' FROM `school` WHERE name='东北大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 80, 275, '' FROM `school` WHERE name='东北大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 60, 310, '408 统考' FROM `school` WHERE name='吉林大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 80, 290, '' FROM `school` WHERE name='吉林大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 80, 320, '408 统考，C9' FROM `school` WHERE name='哈尔滨工业大学'
UNION ALL SELECT id, '软件工程', '083500', 2025, 40, 305, '' FROM `school` WHERE name='哈尔滨工业大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 120, 300, '' FROM `school` WHERE name='哈尔滨工业大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 40, 280, '408 统考' FROM `school` WHERE name='哈尔滨工程大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 70, 270, '' FROM `school` WHERE name='哈尔滨工程大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 50, 305, '408 统考' FROM `school` WHERE name='南京大学'
UNION ALL SELECT id, '软件工程', '083500', 2025, 30, 295, '' FROM `school` WHERE name='南京大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 80, 290, '' FROM `school` WHERE name='南京大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 55, 300, '408 统考' FROM `school` WHERE name='东南大学'
UNION ALL SELECT id, '软件工程', '083500', 2025, 35, 290, '' FROM `school` WHERE name='东南大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 50, 285, '408 统考' FROM `school` WHERE name='南京航空航天大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 90, 275, '' FROM `school` WHERE name='南京航空航天大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 50, 285, '408 统考' FROM `school` WHERE name='南京理工大学'
UNION ALL SELECT id, '软件工程', '083500', 2025, 30, 275, '' FROM `school` WHERE name='南京理工大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 40, 280, '408 统考' FROM `school` WHERE name='苏州大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 80, 270, '' FROM `school` WHERE name='苏州大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 60, 315, '408 统考，C9' FROM `school` WHERE name='浙江大学'
UNION ALL SELECT id, '软件工程', '083500', 2025, 40, 305, '' FROM `school` WHERE name='浙江大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 100, 300, '' FROM `school` WHERE name='浙江大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 40, 270, '双非但就业好' FROM `school` WHERE name='杭州电子科技大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 150, 260, '招生多' FROM `school` WHERE name='杭州电子科技大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 50, 320, '408 统考，C9' FROM `school` WHERE name='中国科学技术大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 80, 300, '' FROM `school` WHERE name='中国科学技术大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 40, 295, '408 统考' FROM `school` WHERE name='厦门大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 60, 285, '' FROM `school` WHERE name='厦门大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 40, 275, '408 统考' FROM `school` WHERE name='福州大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 60, 265, '' FROM `school` WHERE name='福州大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 30, 265, '' FROM `school` WHERE name='福建师范大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 50, 255, '' FROM `school` WHERE name='福建师范大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 35, 265, '' FROM `school` WHERE name='南昌大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 50, 255, '' FROM `school` WHERE name='南昌大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 50, 300, '408 统考' FROM `school` WHERE name='山东大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 80, 285, '' FROM `school` WHERE name='山东大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 40, 285, '408 统考' FROM `school` WHERE name='中国海洋大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 50, 280, '408 统考' FROM `school` WHERE name='郑州大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 80, 270, '' FROM `school` WHERE name='郑州大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 60, 305, '408 统考' FROM `school` WHERE name='武汉大学'
UNION ALL SELECT id, '软件工程', '083500', 2025, 35, 295, '' FROM `school` WHERE name='武汉大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 90, 290, '' FROM `school` WHERE name='武汉大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 70, 310, '408 统考' FROM `school` WHERE name='华中科技大学'
UNION ALL SELECT id, '软件工程', '083500', 2025, 40, 300, '' FROM `school` WHERE name='华中科技大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 120, 295, '' FROM `school` WHERE name='华中科技大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 40, 280, '408 统考' FROM `school` WHERE name='武汉理工大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 80, 270, '' FROM `school` WHERE name='武汉理工大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 40, 290, '408 统考' FROM `school` WHERE name='湖南大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 60, 280, '' FROM `school` WHERE name='湖南大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 55, 295, '408 统考' FROM `school` WHERE name='中南大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 80, 285, '' FROM `school` WHERE name='中南大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 50, 305, '408 统考' FROM `school` WHERE name='中山大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 80, 295, '' FROM `school` WHERE name='中山大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 55, 300, '408 统考' FROM `school` WHERE name='华南理工大学'
UNION ALL SELECT id, '软件工程', '083500', 2025, 35, 290, '' FROM `school` WHERE name='华南理工大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 30, 270, '' FROM `school` WHERE name='深圳大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 100, 260, '双非热门' FROM `school` WHERE name='深圳大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 40, 280, '408 统考' FROM `school` WHERE name='四川大学'
UNION ALL SELECT id, '软件工程', '083500', 2025, 30, 270, '' FROM `school` WHERE name='四川大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 80, 270, '' FROM `school` WHERE name='四川大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 60, 300, '408 统考，电子特色' FROM `school` WHERE name='电子科技大学'
UNION ALL SELECT id, '软件工程', '083500', 2025, 35, 290, '' FROM `school` WHERE name='电子科技大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 120, 285, '' FROM `school` WHERE name='电子科技大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 45, 280, '408 统考' FROM `school` WHERE name='西南交通大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 70, 270, '' FROM `school` WHERE name='西南交通大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 40, 310, '408 统考，C9' FROM `school` WHERE name='西安交通大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 70, 300, '' FROM `school` WHERE name='西安交通大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 50, 300, '408 统考' FROM `school` WHERE name='西北工业大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 80, 290, '' FROM `school` WHERE name='西北工业大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 55, 290, '408 统考，电子特色' FROM `school` WHERE name='西安电子科技大学'
UNION ALL SELECT id, '软件工程', '083500', 2025, 35, 280, '' FROM `school` WHERE name='西安电子科技大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 100, 275, '' FROM `school` WHERE name='西安电子科技大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 35, 270, '408 统考' FROM `school` WHERE name='长安大学'

UNION ALL SELECT id, '计算机科学与技术', '081200', 2025, 35, 280, '408 统考' FROM `school` WHERE name='兰州大学'
UNION ALL SELECT id, '电子信息', '085400', 2025, 50, 270, '' FROM `school` WHERE name='兰州大学';
