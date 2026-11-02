package com.kaoyan;
import com.kaoyan.learning.*;
import com.kaoyan.learning.LearningContracts.*;
import com.kaoyan.entity.PracticeRecord;
import org.junit.jupiter.api.Test;
import java.util.*;
import java.time.*;
import static org.junit.jupiter.api.Assertions.*;
class LearningProfileEngineTest {
 final LearningProfileEngine engine=new LearningProfileEngine();final LocalDateTime at=LocalDateTime.of(2026,10,25,12,0);
 LearningProfileEngine.Evidence evidence(long row,long question,int day,int correct,Integer hint,String difficulty) {
  var r=new PracticeRecord();r.setId(row);r.setQuestionId(question);r.setUserId(1L);r.setIsCorrect(correct);r.setGradingStatus("valid");r.setAnsweredAt(at.plusDays(day));
  r.setQuestionSnapshot(Map.of("id",question,"version",1,"answer","B","content","测试","subject","数据结构","knowledgePoint","树","difficulty",difficulty));
  return new LearningProfileEngine.Evidence(r,hint);
 }
 Cell cell(String diff,double weight) {return new Cell("数据结构","树",LearningProfileEngine.pointId("数据结构","树"),diff,1,weight);}
 @Test void repeatedQuestionInsideSevenDaysIsNotNewEvidence() {
  var rows=List.of(evidence(1,10,0,1,0,"EASY"),evidence(2,10,1,1,0,"EASY"),evidence(3,10,7,0,0,"EASY"));
  var result=engine.calculate(rows,List.of(cell("EASY",1)),"test-v1",1,at.plusDays(8));
  assertEquals(2,result.independentSamples());assertEquals(0.5,result.groups().get(0).masteryIndex());assertEquals(75,result.referenceScore());assertFalse(result.sufficient());
 }
 @Test void assistanceUnknownAndWithdrawnCannotInflateMastery() {
  var withdrawn=evidence(4,4,0,1,0,"EASY");withdrawn.record().setGradingStatus("withdrawn");
  var result=engine.calculate(List.of(evidence(1,1,0,1,1,"EASY"),evidence(2,2,0,1,null,"EASY"),withdrawn),List.of(cell("EASY",1)),"v1",1,at);
  assertEquals(0,result.independentSamples());assertEquals(1,result.assistedSamples());assertEquals(1,result.unknownSamples());assertNull(result.referenceScore());assertNull(result.groups().get(0).masteryIndex());
 }
 @Test void difficultyGroupsStaySeparateAndMissingCellsDoNotRenormalize() {
  var result=engine.calculate(List.of(evidence(1,1,0,1,0,"EASY")),List.of(cell("EASY",0.5),cell("HARD",0.5)),"v1",1,at);
  assertEquals(0.5,result.coverage());assertNull(result.referenceScore());assertEquals(2,result.groups().size());
 }
 @Test void latestFiftyAndOrderIndependentReplay() {
  var rows=new ArrayList<LearningProfileEngine.Evidence>();for(int i=0;i<60;i++)rows.add(evidence(i+1,i+1,i, i<10?0:1,0,"EASY"));
  var first=engine.calculate(rows,List.of(cell("EASY",1)),"v1",1,at.plusDays(60));Collections.reverse(rows);
  assertEquals(first,engine.calculate(rows,List.of(cell("EASY",1)),"v1",1,at.plusDays(60)));assertEquals(50,first.independentSamples());assertEquals(51.0/52,first.groups().get(0).masteryIndex());assertTrue(first.sufficient());
 }
 @Test void anomalyPromptsInvestigationWithoutChangingOfficialGrades() {
  var rows=new ArrayList<LearningProfileEngine.Evidence>();for(int i=0;i<7;i++)rows.add(evidence(i+1,i+1,i,i<5?1:0,0,"EASY"));
  var profile=engine.calculate(rows,List.of(cell("EASY",1)),"v1",1,at.plusDays(7));assertTrue(profile.groups().get(0).anomaly());assertEquals(5,profile.groups().get(0).correct());
 }
 @Test void missingSnapshotsCannotBeReconstructedFromCurrentQuestion() {
  var e=evidence(1,1,0,1,0,"EASY");e.record().setQuestionSnapshot(null);
  var profile=engine.calculate(List.of(e),List.of(),"unpublished",0,at);assertEquals(0,profile.independentSamples());assertNull(profile.referenceScore());
 }
}
