; Call expressions whose function is a member expression, e.g.
; client.chat.completions.create(...). Mirrors python.scm.
(call_expression
  function: (member_expression) @call.callee) @call.expr
