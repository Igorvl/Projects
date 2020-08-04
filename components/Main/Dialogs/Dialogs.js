import React from 'react';
import s from '../../../css/Dialogs.module.css';
import Message from "./Message/Message";
import DialogItem from "./DialogItem/DialogItem";
import userLogo from "../../../Images/logo.svg";
import Icon28Send from '@vkontakte/icons/dist/28/send';
import {Redirect} from "react-router-dom";

export default (props) => {
	let dialogs = props.dialogData.map(d => <DialogItem name={`${d.name} ${d.id}`} id={d.id} key={Math.floor(Math.random()*1000)}/>);
	let messages = props.messageData.map(m =>
		<Message
			msgId={`${m.id} ${m.message}`}
			addNewCommentTxt={props.addNewCommentTxt}
			addNewComment={props.addNewComment}
			newCommentTxt={props.newCommentTxt}
			key={Math.floor(Math.random()*1000)}
		/>);
	
	if (!props.isLoggedIn) return <Redirect to={'/login'}/>;
	return (
		<div className={s.mainDialogs}>
			<div>
				{dialogs}
			</div>
			<div>
				{messages}
				<div>
					<span>Комментировать</span>
					<div className={s.commentBlock}>
						<img src={userLogo} className={s.logo} alt=""/>
						<textarea className={s.messageTxt}
						          onChange={(p)=>{props.addNewCommentText(p.target.value)}}
						          value={props.newCommentTxt}/>
						<Icon28Send onClick={()=>{props.addNewComment()}} className={s.messageBtn} fill={'#264a64'}/>
					</div>
				</div>
			</div>
		</div>
	);
};

