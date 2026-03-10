// Mobile nav toggle
document.addEventListener('DOMContentLoaded', function(){
  const toggle = document.getElementById('navToggle');
  const links  = document.getElementById('navLinks');
  if(toggle && links){
    toggle.addEventListener('click', function(){
      links.classList.toggle('open');
    });
    // Close on link click
    links.querySelectorAll('a').forEach(function(a){
      a.addEventListener('click', function(){ links.classList.remove('open'); });
    });
  }
});
