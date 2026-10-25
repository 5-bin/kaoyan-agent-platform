package com.kaoyan.service.impl;
import com.kaoyan.config.AgentProperties;
import com.kaoyan.entity.Task;
import com.kaoyan.mapper.TaskMapper;
import com.kaoyan.common.ApiException;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
class TaskQuotaExemptionTest {
 @Test void onlyConfiguredUsernameBypassesExhaustedQuota() {
  var mapper = mock(TaskMapper.class);
  var store = new TaskStore(mapper, new AgentProperties());
  when(mapper.countForUserSince(anyLong(), any())).thenReturn(100L);
  when(mapper.quotaUsername(1L)).thenReturn("robin");
  when(mapper.quotaUsername(2L)).thenReturn("student");
  var robin = new Task(); robin.setUserId(1L);
  assertDoesNotThrow(() -> store.begin(robin));
  verify(mapper).insert(robin);
  var other = new Task(); other.setUserId(2L);
  assertThrows(ApiException.class, () -> store.begin(other));
  verify(mapper, never()).insert(other);
 }
 @Test void emptyConfigurationDisablesExemption() {
  var mapper = mock(TaskMapper.class);
  var props = new AgentProperties(); props.setQuotaExemptUsername("");
  assertFalse(new TaskStore(mapper, props).isQuotaExempt(1L));
 }
}
