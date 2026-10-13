package course.kaoyan.catalog;

import course.kaoyan.pojo.entity.practice.Question;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;
import org.springframework.core.annotation.Order;

@Component
@Order(0)
public class PracticeDemoData implements ApplicationRunner {
    private final QuestionRepository questions;
    public PracticeDemoData(QuestionRepository questions) { this.questions = questions; }

    private static String id(String value) {
        return UUID.nameUUIDFromBytes(value.getBytes(StandardCharsets.UTF_8)).toString();
    }
    private static Question q(int order, String subject, String difficulty, String point, String pointName,
            String stem, String a, String b, String c, String d, String answer,
            String explanation, String concept, String approach) {
        return new Question(id("practice-question-" + order), id("practice-version-" + order), subject,
            difficulty, id("knowledge-point-" + point), pointName, stem, a, b, c, d, answer,
            explanation, concept, approach, "408自编演示题（待课程资料负责人复核）",
            "/references/demo-408.html", "自编演示题 Q" + order, order);
    }

    @Override public void run(ApplicationArguments args) {
        if (questions.count() > 0) return;
        questions.saveAll(List.of(
            q(1,"data_structure","easy","stack","栈与队列","栈中元素的典型访问顺序是？","先进先出","后进先出","按优先级访问","随机访问","B","栈通常遵循后进先出原则。","回忆栈顶元素的插入和删除位置。","比较最先入栈元素与最后入栈元素谁先出栈。"),
            q(2,"data_structure","medium","stack","栈与队列","循环队列中设置少用一个存储单元的主要目的是？","提高查找速度","区分队空与队满","支持随机访问","减少入队次数","B","少用一个单元可以用 front==rear 表示队空，并用下一位置等于 front 表示队满。","思考队空和队满时指针关系是否会相同。","尝试分别写出队空与队满的判断式。"),
            q(3,"data_structure","medium","tree","树与遍历","二叉搜索树进行中序遍历通常得到什么序列？","按键值非递减排列","层次顺序","插入顺序","键值非递增排列","A","二叉搜索树左子树键值较小、右子树键值较大，中序遍历依次访问左、根、右。","中序遍历的顺序是左子树、根、右子树。","结合二叉搜索树的大小关系判断输出次序。"),
            q(4,"computer_organization","easy","storage","存储层次","Cache 的主要作用是缓解哪一矛盾？","CPU与主存速度不匹配","主存与硬盘容量相同","指令与数据无法区分","总线不能传输地址","A","Cache 利用局部性保存近期常用数据，缓解CPU与主存之间的速度差距。","关注存储层次中速度与容量的差异。","判断哪两个部件之间存在明显速度差。"),
            q(5,"computer_organization","medium","number","数据表示","8位补码 11111111 表示的十进制数是？","255","-127","-1","0","C","补码全1表示-1。","补码负数可按取反加一还原其绝对值。","对11111111取反加一，观察得到的绝对值。"),
            q(6,"computer_organization","medium","cpu","CPU与指令","程序计数器 PC 通常保存什么？","当前操作数","下一条待执行指令地址","当前指令操作码","栈顶数据","B","PC用于指出下一条将要取出的指令地址。","取指周期需要知道下一条指令的位置。","判断哪个寄存器负责提供取指地址。"),
            q(7,"operating_system","easy","process","进程与线程","同一进程中的线程通常共享哪项资源？","各自的程序计数器","各自的栈","进程地址空间","各自的寄存器现场","C","同一进程中的线程共享进程地址空间和多数进程资源，但保留各自栈及寄存器现场。","区分进程资源与线程执行现场。","逐项判断哪些内容必须由每个线程独立保存。"),
            q(8,"operating_system","medium","scheduling","进程调度","时间片轮转调度最直接适合哪类系统？","批处理系统","交互式分时系统","无中断系统","仅运行一个进程的系统","B","时间片轮转通过周期性切换提高交互任务的响应公平性。","关注时间片对响应时间和公平性的影响。","判断哪类系统最重视多个用户任务的及时响应。"),
            q(9,"operating_system","medium","deadlock","死锁","破坏循环等待条件的一种常见方法是？","允许资源抢占","统一规定资源申请顺序","增加进程数量","取消互斥资源","B","为资源规定全序并按序申请，可以破坏循环等待条件。","死锁四个必要条件之一是循环等待。","寻找能让资源等待关系无法形成环的方法。"),
            q(10,"computer_network","easy","tcp","TCP可靠传输","TCP确认号通常表示什么？","已经收到的最后一个字节本身","期望收到的下一个字节序号","发送窗口大小","报文段总长度","B","TCP采用累计确认，确认号表示接收方期望收到的下一个字节序号。","累计确认关注连续收到的数据边界。","如果前N个字节均收到，接收方下一步期待哪个序号？"),
            q(11,"computer_network","medium","network-layer","网络层","路由器转发IP数据报时主要依据什么？","源端口号","目的IP地址","应用层协议名称","源MAC地址","B","路由器根据目的IP地址查找转发表并决定下一跳。","区分网络层地址和传输层端口。","判断路由表中的匹配键属于哪一层。"),
            q(12,"computer_network","medium","dns","应用层协议","DNS 的核心作用是？","保证TCP可靠传输","完成域名到IP地址等信息的解析","加密所有HTTP内容","分配以太网MAC地址","B","DNS提供域名与IP地址等资源记录之间的查询解析。","考虑用户输入域名后主机首先需要获得什么。","区分名称解析、传输可靠性和链路层地址分配。")
        ));
    }
}
