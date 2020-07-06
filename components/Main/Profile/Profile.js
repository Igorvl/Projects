import React, {useEffect, useState} from 'react';
import s from '../../../css/Profile.module.css';
import ProfileInfo from "./ProfileInfo/ProfileInfo";
import MyPostsContainer from "./MyPosts/MyPostsContainer";
import * as axios from "axios";

export default (props) => {
	
	return (
		<div className={s.mainProfile}>
			<div>
				<ProfileInfo choosedUser={props.choosedUser} userId={props.userId}/>
				<MyPostsContainer/>
			</div>
		</div>
	)
};

