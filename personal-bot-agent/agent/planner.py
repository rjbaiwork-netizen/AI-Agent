def make_plan(task):
 task=task.strip()
 return [] if not task else [f'Clarify outcome: {task}','Break work into verifiable steps','Execute permitted actions','Review results']
