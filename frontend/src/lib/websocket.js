import { base } from './api';
export function subscribe(callId, onEvent, onConnection) {
  let socket, timer, closed=false, attempts=0;
  function connect() {
    socket=new WebSocket(`${base.replace(/^http/,'ws')}/ws/calls/${encodeURIComponent(callId)}`);
    socket.onopen=()=>{attempts=0;onConnection('connected');};
    socket.onmessage=event=>{
      const message=JSON.parse(event.data);
      onEvent(message);
      if(message.type==='chunk_complete')requestAnimationFrame(()=>requestAnimationFrame(()=>{
        if(socket.readyState===WebSocket.OPEN)socket.send(JSON.stringify({type:'ack',chunk_id:message.payload.chunk_id}));
      }));
    };
    socket.onerror=()=>onConnection('connection error');
    socket.onclose=()=>{
      if(closed)return;
      onConnection('disconnected; retrying');
      if(attempts++<5)timer=setTimeout(connect,Math.min(1000*2**attempts,10000));
      else onConnection('disconnected; reconnect manually');
    };
  }
  connect();
  return ()=>{closed=true;clearTimeout(timer);socket?.close();};
}
