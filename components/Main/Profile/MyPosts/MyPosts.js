import React from 'react';
import s from '../../../../css/MyPosts.module.css';
import Post from "./Post/Post";

export default (props) => {
	
	let posts = props.postData.map(p => <Post id={p.id} msg={p.msg} like={p.like} dislike={p.dislike} key={p.id}/>);
	
	return (
		<div>
			<span>Ввести комментарий</span>
			<div>
				<textarea value={props.newMsgTxt} onChange={(p)=> props.addNewPostText(p.target.value)} name="#"cols="60" rows="5"/>
			</div>
			<button onClick={()=>props.addPost()} className={s.postBtn}>Add post</button>
			
			<div className={s.posts}>
				{posts}
			</div>
		</div>
	);
};

