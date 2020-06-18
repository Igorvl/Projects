import React from 'react';
import s from '../../../../css/Message.module.css';


export default (props) => {
	
	return (
		<div>
			<div className={s.commentTxt}>Message {props.msgId}</div>
			{/*<div>*/}
			{/*	<span>Комментировать</span>*/}
			{/*	<div className={s.commentBlock}>*/}
			{/*		<img src={logo} className={s.logo} alt=""/>*/}
			{/*		<textarea className={s.messageTxt}*/}
			{/*		          onChange={(p)=>{*/}
			{/*		          		props.addNewCommentTxt(p.target.value)}}*/}
			{/*		          value={props.newCommentTxt}/>*/}
			{/*		<Icon28Send onClick={props.addNewComment} className={s.messageBtn} fill={'#264a64'}/>*/}
			{/*	</div>*/}
			{/*</div>*/}
		</div>
	)
};



