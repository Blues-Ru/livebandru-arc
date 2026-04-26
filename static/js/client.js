$(document).ready(function(){
	C.init();
	/*
		$("#fastsearchBox").each(function() {
			if ($(this).val() == 'искать')
				$(this).css("color", "#999");
			
			$(this).focus(function() {
				if ($(this).val() == 'искать')
					$(this).val('').css("color", "#000");
			});
		});
	*/
})

var C={
	init: function(){
		C.auth.init();
		C.mediator.init();
		$("a.HelpLink").click(function(){
		  $("a.HelpLink").toggle();
		  $("#Help").toggle();
		  return false;
		});
	},

	auth: {
		location: null,//адрес перехода после авторизации, чтобы можно было повесить запрос авторизации на ссылку
		callback: null,//скрипт, который выполняется после авторизации
		auth_popup_win: null,//ссылка на окно авторизации, чтобы можно было его закрыть или дать фокус
		init: function(){
			$('#logRegForm input[name=email]').evSwitchField();
			//.add('#updateLogReg').add('#forum form.forumLogReg')
			$('#logRegForm').bind('submit',function(evt){
				C.auth.location=null;
				C.auth.popup(evt);
			});
			$('#loggedIn a').bind('click',C.auth.popup);
		},
		
		userLoggedIn: function(){
			var bool=$('#loggedIn').length>0
			return bool;
		},
		
		/*
			<a href="/my/link/" onclick="return C.auth.checkGo(this)">...</a>
			метод можно повесить на ссылку, тогда при клике произойдет проверка автоизации
			если юзер не авторизован - покажется окно авторизации
		*/
		checkGo: function(link){
			if(!C.auth.userLoggedIn()){
				C.auth.location=link.href;
				C.auth.popup();
				return false;
			}
		},

		/*
			показываем окно авторизации (или даем фокус) 
			и запускаем проверку изменения статуса (логин/логаут)
			как только статус меняется - закрываем окно и делаем релоад или редирект
		*/
		popup: function(evt){
			if(evt){evt.preventDefault();}
			if(!C.auth.auth_popup_win || C.auth.auth_popup_win.closed){
				C.auth.auth_popup_win=$.popup('',800,500,{name:'auth_popup',resize:1});
			}
			C.auth.auth_popup_win.focus();
			if(!C.auth.userLoggedIn()){
				$('#logRegForm').attr({target:'auth_popup'})[0].submit();
				C.auth.checkLogin();
			}else{
				C.auth.auth_popup_win.location.href='/auth';
				C.auth.checkLogout();
			}
		},

		/*
			проверяем изменение статуса на логин, как только статус изменится, делаем релоад 
			или редирект
		*/
		checkLogin: function(){
			if($.getCookie('lbauth')){
				C.auth.auth_popup_win.close();
				if(C.auth.location){
					location.href=C.auth.location;
				}else if(C.auth.callback){
					C.auth.callback();
				}else{
					location.reload();
				}
			}else if(!C.auth.auth_popup_win.closed){
				setTimeout('C.auth.checkLogin()',100)
			}
		},

		/*
			проверяем изменение статуса на логаут, как только статус изменится, делаем релоад
		*/
		checkLogout: function(){
			if(!$.getCookie('lbauth')){
				C.auth.auth_popup_win.close();
				location.href='/all';
			}else if(!C.auth.auth_popup_win.closed){
				setTimeout('C.auth.checkLogout()',100)
			}
		}
	},
	
	mediator: {
		init: function(){
			var $mediator_form=$('#mediatorSwitcherForm');
			if($mediator_form.length){
				$mediator_form.bind('submit',function(evt){
					evt.preventDefault();
					if(C.auth.userLoggedIn()){
						//если пользователь авторизован, добавляем/удаляем в Мое
            var $mediator=$('#mediatorSwitcherForm h1 input[type=image]').eq(0);
			      if ($mediator.length){
						  C.mediator.toggle($mediator);
						}
					}else{
						//если не авторизован, то сперва выполняем авторизацию
						//и после авторизации выполняем отправку формы
						C.auth.callback=function(){
							evt.target.submit();
						}
						C.auth.popup();
					}
				});
			}
			$('.favPickForm').each(function(){
			  $(this).bind('submit', function(evt){
					evt.preventDefault();
          $(this).find('input[type=image]').each(function(){
  				  C.mediator.toggle($(this));
          });
			  });
			});
		},

		toggle: function($mediator){
			var one_or_zero=($mediator.hasClass('nofv'))?'1':'0';
			var action=$mediator.parents('form').eq(0).attr('action');
			var url=action.substr(0,action.length-2);
			$.ajax({
				url: url,
				type: 'POST',
				data: {fav:one_or_zero},
				success: function(get){
					var hash=C.mediator.get2hash(get);
					if(hash.code==0){
						$mediator.toggleClass('nofv').toggleClass('fv');
						C.mediator.image($mediator);
					}
				}
			})
		},
		
		image: function($mediator){
			if($mediator.hasClass('nofv')){
				var src='/stage/img/add2mine.gif';
			}else{
				var src='/stage/img/mine.gif';
			}
			$mediator.attr({src:src});
		},
		
		get2hash: function(get){
			var arr=get.split('&');
			var hash={};
			if(arr.length){
				for(var i=0; i<arr.length; i++){
					var key=arr[i].split('=')[0];
					var value=arr[i].split('=',2)[1];
					hash[key]=value;
				}
			}
			return hash;
		}
	}
}
