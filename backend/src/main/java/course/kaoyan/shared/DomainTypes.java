package course.kaoyan.shared;

/** API枚举与设计文档一致；枚举存在不表示对应业务已实现。 */
public final class DomainTypes {
    private DomainTypes() {}
    public enum TaskType { knowledge_qa, school_recommendation, wrong_question_tutor }
    public enum Subject { data_structure, computer_organization, operating_system, computer_network }
    public enum DegreeType { academic, professional }
    public enum RegionConstraint { required, preferred }
    public enum Difficulty { easy, medium, hard }
    public enum PracticeMode { chapter, random, wrong, favorite }
    public enum PracticeStatus { active, completed }
    public enum WrongStatus { reviewing, mastered }
    public enum ReviewStatus { approved, rejected, withdrawn }
}
