; Call expressions whose function is an attribute chain, e.g.
; client.chat.completions.create(...). Plain identifier calls (foo())
; can never be a tracked SDK call, so they're excluded at the query level.
(call
  function: (attribute) @call.callee) @call.expr
