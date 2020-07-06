import MyPosts from "./MyPosts";
import {addNewPostText, addPost} from "../../../Redux/profileReducer";
import {connect} from "react-redux";


const mapStateToProps = (state) => {
	return ({
		postData: state.profilePage.postData,
	})
};

export default connect(mapStateToProps, {addNewPostText, addPost})(MyPosts)
