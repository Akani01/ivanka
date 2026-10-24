(function(){
 'use strict';
 const form=document.getElementById('newsletterForm');
 if(form){
  const url=document.body.dataset.newsletterApi||'';
  if(!url){const b=form.querySelector('button');b.textContent='Email us';b.setAttribute('aria-label','Enquire about email updates');}
  form.addEventListener('submit',async function(e){
   e.preventDefault(); if(!form.reportValidity())return;
   const field=form.querySelector('input[type="email"]'),email=field.value.trim(),button=form.querySelector('button');
   function message(text){let box=form.parentElement.querySelector('.iv-newsletter-message');if(!box){box=document.createElement('p');box.className='iv-newsletter-message';box.setAttribute('role','status');form.after(box);}box.textContent=text;}
   if(!url){const contact=document.body.dataset.contactUrl||'/contact/';message('Please contact our team about collection updates.');const a=document.createElement('a');a.href=contact;a.textContent='Open contact details';a.style.textDecoration='underline';form.parentElement.querySelector('.iv-newsletter-message').append(' ',a);return;}
   button.disabled=true;
   try{
    const m=document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/),hidden=document.querySelector('[name=csrfmiddlewaretoken]');
    const token=m?decodeURIComponent(m[1]):(hidden?hidden.value:'');
    const res=await fetch(url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':token,Accept:'application/json'},body:JSON.stringify({email})});
    const data=await res.json().catch(()=>({}));
    if(!res.ok||!data.success)throw new Error(data.error||data.detail||'Subscription is unavailable. Please contact the team.');
    message('Subscribed. Check your inbox.');field.value='';
   }catch(err){message(err.message||'Unable to subscribe. Please contact the team.');}finally{button.disabled=false;}
  });
 }
 if(!document.getElementById('authVeil')&&'serviceWorker' in navigator&&document.body.dataset.swUrl){window.addEventListener('load',()=>navigator.serviceWorker.register(document.body.dataset.swUrl,{scope:document.body.dataset.storeHome||'/'}).catch(()=>{}));}
})();
